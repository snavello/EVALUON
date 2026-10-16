"""Ajuste único del paso 2 en la matriz (T-285; REQ-119; spec 016; plan 016, «Paso 2»; ADR-0070).

La medición T-283 mostró definiciones que la extracción y el filtro no aplicaban (D-283-1 a D-283-4).
Se corrigen como definiciones generales, en el bloque común (`matriz-definiciones-v10`), la extracción
(`matriz-extraccion-v14`) y el filtro (`matriz-filtro-v11`), nunca como ejemplos ni reglas copiadas de
un caso: estas pruebas miran la instrucción **vigente** (la que fija `MATRIX_PROMPT_VERSIONS`), así que
fallan con las versiones de T-279 y T-280 y pasan con las nuevas. Los textos de prueba son inventados
(P4); el no calco contra los casos lo prueba `tests/test_instrucciones_sin_casos.py`.
"""

import re

from evaluon.tenders.proposal import extraction
from evaluon.tenders.proposal import filter as row_filter


def _block():
    """El bloque común de definiciones vigente, tal como lo incluye el código."""
    return extraction.load_instruction("extraccion").text


def _motive_line(text, motive):
    """La línea de la instrucción que define el motivo de descarte `motive`."""
    return next(line for line in text.splitlines()
                if re.match(rf'^\s*-\s+"?{motive}"?:', line))


# --- D-283-1: la presentación física es requisito; la carga en el Portal, forma de presentar ------


def test_d283_1_the_block_tells_the_physical_delivery_from_the_portal_upload():
    """REQ-119 (D-21, D-12; decisión del 2026-10-12, «si requiere presentacion fisica y no la hace
    (…) la oferta no cumple»): el bloque vigente dice que, en una misma oración, la carga en el Portal
    es forma de presentar y la entrega en papel de lo que el Portal marca «Requiere presentar» es
    requisito."""
    text = _block()

    assert "entregar en papel lo que el Portal marca como «Requiere presentar»" in text
    assert "la carga es forma de presentar; la entrega física, requisito" in text


def test_d283_1_the_portal_motive_never_covers_the_physical_delivery():
    """REQ-119 (D-21, D-12): en la extracción y en las dos preguntas del filtro, el motivo
    `forma_presentacion_portal` es cómo se carga la oferta en el Portal y nunca la entrega en papel
    que la oración también pide, aunque dependa de lo que marque el Portal."""
    texts = [extraction.load_prompt("extraccion"), row_filter.load_prompts()[0]]

    for text in texts:
        line = _motive_line(text, "forma_presentacion_portal")
        assert "cómo se carga, se sube o se completa la oferta en el Portal" in line
        assert "nunca la entrega en papel" in line
        assert "aunque dependa de lo que marque el Portal" in line
