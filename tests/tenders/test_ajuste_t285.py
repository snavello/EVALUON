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


# --- D-283-2: la condición de una opción entra como condición de esa opción y no se descarta ------


def test_d283_2_the_block_says_the_decision_on_options_literally():
    """REQ-119 (D-13; spec 015, 2026-10-10, «Requisito de la forma elegida»: la condición de una opción
    «entra solo como condición de esa opción; la oración que le exige algo a quien usa la opción se
    mantiene»): el bloque vigente lo dice con la decisión literal."""
    text = _block()

    assert ("entra solo como condición de esa opción: la oración que le exige algo a quien usa la "
            "opción se mantiene, con el nombre de la opción") in text


def test_d283_2_the_optional_motive_is_only_for_a_sentence_that_demands_nothing():
    """REQ-119 (D-13): en la extracción y en el filtro, `condicion_opcional` es solo la oración que
    permite o describe una opción sin exigirle nada a quien la usa; la que le exige algo es requisito
    de esa opción (extracción) y se mantiene (filtro)."""
    extraction_line = _motive_line(extraction.load_prompt("extraccion"), "condicion_opcional")
    filter_line = _motive_line(row_filter.load_prompts()[0], "condicion_opcional")

    assert "no le exige nada a quien la usa" in extraction_line
    assert "la que le exige algo es requisito de esa opción" in extraction_line
    assert "no le exige nada a quien la usa" in filter_line
    assert "la fila que le exige algo a quien usa la opción se mantiene" in filter_line


def test_d283_2_the_filter_sees_the_option_of_the_row_and_its_instruction_says_what_to_do():
    """REQ-119 (D-13): la fila que la extracción propuso como condición de una opción llega al filtro
    con su línea «Opción:», y las dos preguntas del filtro dicen que esa fila se mantiene si le exige
    algo a quien usa la opción. Una fila sin opción no trae la línea (texto inventado)."""
    from types import SimpleNamespace

    from evaluon.tenders.proposal.extraction import Found

    segment = SimpleNamespace(pk=1, key="sec-i/9.1", path="Sección I > 9", label="",
                              section_class="",
                              text="Quien ofrezca piezas de otro taller deberá nombrar ese taller.")
    unit = SimpleNamespace(segment=segment, document_title="Pliego inventado")
    with_option = row_filter.Row(unit, Found("formal", (0, 61), option="subcontratacion"), 1)
    without = row_filter.Row(unit, Found("formal", (0, 61)), 1)

    shown = row_filter.render_block("F1", with_option)

    assert "Opción: subcontratacion" in shown
    assert shown.index("Clase propuesta:") < shown.index("Opción:") < shown.index("Fragmento:")
    assert "Opción:" not in row_filter.render_block("F1", without)
    for text in row_filter.load_prompts():
        assert "a veces la «Opción:» de la que es condición" in text
        assert ("Una fila con «Opción:» es la condición de esa opción y se evalúa como tal: se "
                "mantiene si le exige algo a quien usa la opción") in text


def _verdict(option, a_motive="condicion_opcional", answer="no"):
    from types import SimpleNamespace

    from evaluon.tenders.proposal.extraction import Found

    text = "Quien ofrezca piezas de otro taller deberá nombrar ese taller junto con su oferta."
    segment = SimpleNamespace(pk=1, key="sec-i/9.1", path="", label="", section_class="",
                              text=text, char_start=0, char_end=len(text))
    unit = SimpleNamespace(segment=segment, document_title="Pliego inventado")
    row = row_filter.Row(unit, Found("formal", (0, len(text)), option=option), 1)
    a = {"razonamiento": "r", "decision": "descartar", "motivo": a_motive,
         "indicio": "Quien ofrezca piezas de otro taller deberá nombrar"}
    return row_filter.decide(row, a, {"razonamiento": "r", "respuesta": answer})


def test_d283_2_a_row_of_an_option_is_never_discarded_as_an_optional_condition():
    """REQ-119 (D-13, D-15; regla del filtro `filtro-v5`): si A descarta por `condicion_opcional` una
    fila que la extracción propuso como condición de una opción, la fila no se pierde: va a
    sugerencia con `no_coinciden` y la anomalía; sin opción, el mismo descarte sigue descartando, y
    la fila con opción descartada por otro motivo también."""
    kept = _verdict("subcontratacion")
    assert kept.destination == row_filter.SUGERENCIA
    assert kept.doubt_reason == "no_coinciden"
    assert kept.anomaly == row_filter.ANOMALY_OPTION_DISCARDED

    assert _verdict("").destination == row_filter.DESCARTADA
    assert _verdict("subcontratacion", a_motive="consecuencia_sancion").destination == (
        row_filter.DESCARTADA)
    assert row_filter.RULE_VERSION == "filtro-v5"
