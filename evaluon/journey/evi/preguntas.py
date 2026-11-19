"""«Pregúntele a Evi» (feature 020, REQ-171 a REQ-173; T-368; ADR-0082): una pregunta, una respuesta de la IA
local.

Es una función experimental, por el carril liviano. Lo que la separa de todo lo demás:

- Instrucción propia (`prompts/evi-v1.txt`), en su carpeta. Una versión publicada no se modifica: un cambio es
  un archivo nuevo. Ninguna otra etapa la usa, y esta no usa las de la evaluación, la matriz ni la Consulta.
- Contexto: SOLO los textos fijos de `textos.py` y, con un procedimiento abierto, el estado que arma `panel.py`
  (el de la portada). Nada de pliegos, ofertas ni normativa, y sin recuperación (ni embeddings ni reranker).
- Solo la IA local (P4, P5): el pedido sale por `generation.generate`, el motor de `GENERATION_URL`. Este módulo
  no importa `evaluon.ai.external`.
- Un solo motor (ADR-0057): como la Consulta, si el motor de lotes está ocupado con un trabajo o no responde
  (`queries.services.consulta_notice`), no se pide y se avisa. El pedido espera `EVI_TIMEOUT_SECONDS` (50 s por omisión).
- La salida se tiene por texto: la vista la muestra escapada, nunca como HTML.
- Evi no decide ni recomienda: lo dice la instrucción; el código no puede garantizarlo, por eso la función es
  experimental y rotulada, y las tres preguntas trampa se corren una vez contra la IA real
  (`manage.py evi_preguntas`).
"""

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings

from evaluon.ai import AIServiceError, generation
from evaluon.journey.evi import panel, textos
from evaluon.journey.proceso import pasos

PROMPT_VERSION = "evi-v1"
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

MAX_QUESTION_CHARS = 300
MAX_OUTPUT_TOKENS = 450
MAX_ANSWER_CHARS = 1500

SCHEMA = {
    "type": "object",
    "properties": {"respuesta": {"type": "string"}},
    "required": ["respuesta"],
    "additionalProperties": False,
}

GUIDE_SOURCE = "la guía de Evi"

# Del estado que se le manda al modelo se saca lo que empuja a recomendar (verificación del lote, C-3): cuál es
# la oferta más baja o más alta y los nombres de los oferentes. El panel los sigue mostrando.
_NOMBRE_DE_OFERENTE = re.compile(r"(Oferta \d+) \([^)]*\)")


def limpio(texto):
    """El texto de estado para el modelo: sin el nombre del oferente y `""` si dice cuál es la más baja o la
    más alta."""
    if re.search(r"más (baja|alta)", texto, re.I):
        return ""
    return _NOMBRE_DE_OFERENTE.sub(r"\1", texto)


@dataclass
class Resultado:
    ok: bool
    respuesta: str = ""
    motivo: str = ""  # por qué falló, para el registro
    fuente: str = ""  # «Basada en: …»
    modelo: str = ""
    version: str = PROMPT_VERSION
    segundos: float = 0.0
    contexto_caracteres: int = 0


def instrucciones(version=PROMPT_VERSION):
    return (PROMPTS_DIR / f"{version}.txt").read_text(encoding="utf-8").strip()


def guia():
    """La guía: los textos fijos de Evi, tal cual los ve la persona."""
    lineas = ["GUÍA DE EVI", "",
              f"{textos.CIRCUITO_TITULO}. {textos.CIRCUITO_QUE_ES}", f"Cómo se lee: {textos.CIRCUITO_COMO_SE_LEE}",
              f"{textos.CIRCUITO_QUIEN_DECIDE.titulo}: {textos.CIRCUITO_QUIEN_DECIDE.texto}",
              f"{textos.ESTADOS_TITULO}:"]
    lineas += [f"- {nombre}: {texto}" for nombre, texto in textos.ESTADOS_SIGNIFICADO]
    lineas.append("")
    for definicion in pasos.PASOS:
        n = definicion.numero
        t = textos.PASOS[n]
        lineas.append(f"Paso {n}: {definicion.nombre}")
        lineas.append(f"Qué es: {t.que_es}")
        lineas.append(f"Para qué sirve: {t.sirve}")
        lineas.append("Qué hay que hacer:")
        lineas += [f"- {h}" for h in t.hacer]
        for termino in t.terminos:
            lineas.append(f"{termino.titulo}: {termino.texto}")
        lineas.append("")
    return "\n".join(lineas).strip()


def estado(proceso):
    """El estado del procedimiento abierto, con lo mismo que muestra «Qué hacer acá»."""
    lineas = ["ESTADO DEL PROCEDIMIENTO ABIERTO", f"Procedimiento: {proceso.procedure.number}", ""]
    for nodo in panel.nodos(proceso):
        lineas.append(f"Paso {nodo.numero} ({nodo.nombre}): {nodo.estado_texto}. {limpio(nodo.dato)}".rstrip())
        aca = nodo.aca
        if not aca:
            continue
        for frase in (limpio(aca.resumen), limpio(aca.espera)):
            if frase:
                lineas.append(f"  {frase}")
        if aca.pendientes:
            lineas.append("  Falta hacer:")
            lineas += [f"  - {limpio(texto)}" for texto in aca.pendientes if limpio(texto)]
        else:
            lineas.append("  No hay nada pendiente en este paso.")
        lineas += [f"  Aviso: {limpio(texto)}" for texto in aca.avisos if limpio(texto)]
    return "\n".join(lineas)


def mensajes(pregunta, proceso=None):
    """Los dos mensajes del pedido: la instrucción y, aparte, la guía, el estado (si hay) y la pregunta."""
    partes = [guia()]
    if proceso is not None:
        partes.append(estado(proceso))
    partes.append(f"PREGUNTA\n{pregunta}\nFIN DE LA PREGUNTA")
    return [{"role": "system", "content": instrucciones()},
            {"role": "user", "content": "\n\n".join(partes)}]


def fuente(proceso=None):
    if proceso is None:
        return GUIDE_SOURCE
    return f"{GUIDE_SOURCE} y el estado del procedimiento {proceso.procedure.number}"


def validar(pregunta):
    """El mensaje de por qué no se acepta la pregunta, o `""` si se acepta. No depende del modelo."""
    if not pregunta.strip():
        return textos.PREGUNTA_VACIA
    if len(pregunta) > MAX_QUESTION_CHARS:
        return f"La pregunta es demasiado larga: el máximo es de {MAX_QUESTION_CHARS} caracteres."
    return ""


def preguntar(pregunta, proceso=None):
    """Pide la respuesta a la IA local. No lanza: cualquier falla vuelve como `Resultado(ok=False)`.
    `proceso`: el `calculo.Proceso` del procedimiento abierto, o `None`."""
    from evaluon.queries import services  # importa el motor y la cola igual que la Consulta
    pedido = mensajes(pregunta.strip(), proceso)
    resultado = Resultado(ok=False, fuente=fuente(proceso),
                          modelo=generation.model_for(settings.GENERATION_URL),
                          contexto_caracteres=sum(len(m["content"]) for m in pedido))
    inicio = time.monotonic()
    try:
        aviso = services.consulta_notice()
        if aviso:
            resultado.motivo = f"motor no disponible: {aviso}"
            return resultado
        salida = generation.generate(pedido, SCHEMA, max_tokens=MAX_OUTPUT_TOKENS,
                                     timeout=settings.EVI_TIMEOUT_SECONDS)
    except AIServiceError as error:
        resultado.motivo = error.reason
        return resultado
    finally:
        resultado.segundos = round(time.monotonic() - inicio, 2)
    resultado.modelo = salida.request.get("model", resultado.modelo)
    try:
        if salida.finish_reason == "length":
            raise ValueError("cortada")
        texto = json.loads(salida.content)["respuesta"]
        if not isinstance(texto, str) or not texto.strip():
            raise ValueError("vacía")
    except (ValueError, KeyError, TypeError):
        resultado.motivo = "invalid_output"
        return resultado
    resultado.ok = True
    resultado.respuesta = texto.strip()[:MAX_ANSWER_CHARS]
    return resultado
