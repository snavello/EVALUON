"""Ajuste único de la matriz externa (T-294; REQ-123; plan 016, «Paso 3»; ADR-0025, ADR-0066 a
ADR-0068, ADR-0070): los hallazgos D-293-1 a D-293-5 y O-293-2 de la medición T-293 (ronda 1 del
paso 3, que no pasó la puerta 16), uno por grupo de pruebas.

Con el caso chico (`tests/assessment/data/caso-chico/`, inventado y público) y el doble del cliente
externo (`fake_external`, sin red: la suite bloquea toda llamada real). Todo el texto es inventado
(P4).
"""

import pytest
from django.conf import settings

from evaluon.tenders import models as m
from evaluon.tenders.proposal import external
from tests.tenders.scripted import propose, script  # noqa: F401  (fixture)
from tests.tenders.test_external_matrix import (  # noqa: F401  (fixtures y ayudas)
    QUOTATION,
    ExternalScript,
    ext,
    rows_of,
    small_case,
)

pytestmark = pytest.mark.django_db

VERSION = "matriz-externa-v2"
PORTAL_RULE = "Una oración que solo permite una opción o solo dice cómo se carga en el Portal"
FILTER_RULE = "si solo la permite o dice cómo se carga en el Portal, se descarta"


class OptionScript(ExternalScript):
    """Como `ExternalScript`, pero el requisito del tramo que contiene `needle` sale con la opción
    `option` (el modelo que arma una fila de una opción que solo se permite)."""

    def __init__(self, fake, monkeypatch, needle, option):
        super().__init__(fake, monkeypatch)
        self.needle, self.option = needle, option

    def _segment(self, alias, text):
        answer = super()._segment(alias, text)
        if self.needle in text:
            for requirement in answer["requisitos"]:
                requirement["opcion"] = self.option
        return answer


# --- La instrucción en uso ---------------------------------------------------------------------


def test_the_external_instruction_in_use_is_v2():
    """REQ-123 (T-294): `EXTERNAL_PROMPT_VERSIONS` apunta a `matriz-externa-v2` y la etapa carga esa
    versión, con el bloque de definiciones puesto donde tiene la marca; la v1 sigue publicada."""
    instruction = external.load_instruction()

    assert settings.EXTERNAL_PROMPT_VERSIONS["matriz"] == VERSION
    assert instruction.version == VERSION
    assert "{{DEFINICIONES}}" not in instruction.text
    assert instruction.text.startswith("Ayudás a la Comisión Evaluadora")


# --- D-293-1: una opción que solo se permite no es una fila -------------------------------------


def test_d_293_1_the_instruction_says_that_an_option_that_only_permits_is_not_a_row():
    """REQ-123, D-293-1 (D-13, D-12, D-21): la extracción y el control de filas de la v2 dicen que
    la oración que solo permite una opción, o solo dice cómo se carga en el Portal, no es
    requisito (y que la fila con opción que solo eso dice se descarta)."""
    text = external.load_instruction().text

    assert PORTAL_RULE in text
    assert FILTER_RULE in text


def test_d_293_1_the_request_carries_the_rule_and_the_row_of_a_permitted_option_is_not_firm(
        small_case, operator_user, fake_external, monkeypatch):  # noqa: F811
    """REQ-123, D-293-1: el pedido que sale lleva la regla de la v2 en su sistema; si el modelo arma
    una fila con `opcion` = `descuento` en un tramo que solo permite la opción y el control la baja
    por `forma_presentacion_portal`, la fila no queda firme: queda descartada con su indicio."""
    fake_external.enable("matriz")
    script = OptionScript(fake_external, monkeypatch, QUOTATION, "descuento")
    script.rows[QUOTATION] = {"destino": "descartada", "motivo": "forma_presentacion_portal",
                              "indicio": QUOTATION, "razonamiento": "Solo dice cómo se carga."}

    requested, job = propose(operator_user, small_case.procedure)

    assert job.status == "done", job.error
    run = requested.run
    assert all(PORTAL_RULE in payload.system and FILTER_RULE in payload.system
               for payload in script.payloads)
    assert run.prompt_versions["externo"]["matriz"] == VERSION
    assert not any(QUOTATION in row.quotes.get(order=1).text for row in rows_of(run))
    discarded = m.DiscardedRow.objects.get(run=run)
    assert discarded.reason == "forma_presentacion_portal" and discarded.evidence_text == QUOTATION


def test_d_293_1_a_row_of_an_option_dropped_as_optional_goes_to_review_not_to_firm(
        small_case, operator_user, fake_external, monkeypatch):  # noqa: F811
    """REQ-123, D-293-1: si el control baja la fila con `opcion` por `condicion_opcional` (la
    oración solo permite la opción), la guarda de código la manda a revisión como sugerencia
    (`no_coinciden`, anomalía `filtro_opcion_descartada`) y no queda firme."""
    fake_external.enable("matriz")
    script = OptionScript(fake_external, monkeypatch, QUOTATION, "descuento")
    script.rows[QUOTATION] = {"destino": "descartada", "motivo": "condicion_opcional",
                              "indicio": QUOTATION, "razonamiento": "Solo permite el descuento."}

    requested, job = propose(operator_user, small_case.procedure)

    assert job.status == "done", job.error
    run = requested.run
    firm = [row for row in rows_of(run, state="propuesto")
            if QUOTATION in row.quotes.get(order=1).text]
    suggested = [row for row in rows_of(run, state="sugerido")
                 if QUOTATION in row.quotes.get(order=1).text]
    assert firm == [] and len(suggested) == 1
    assert suggested[0].doubt_reason == "no_coinciden"
