"""La línea «Etapas fuera del equipo» en el detalle del par de la pestaña de evaluación (REQ-122,
P6; plan 016, "Modelo de datos"; T-300). Caso chico inventado; la clave `externo` de la corrida se
simula, porque la escriben T-291 y T-299."""

import pytest
from django.urls import reverse

from tests.assessment.test_export import (
    NONE_LINE,
    VERIFIER_LINE,
    add_external_run,
    external_key,
)
from tests.assessment.test_matrix import add_run, open_matrix, requirement, three  # noqa: F401
from tests.journey.temas.test_s4_propuesta import log_in

pytestmark = pytest.mark.django_db


def test_the_pair_in_the_tab_says_which_stages_ran_outside_the_equipment(
        client, three, procedure, operator_user):
    """REQ-122: el detalle del par del recorrido trae una sola línea con proveedor, modelo, modo y
    pedidos de la etapa que corrió fuera, o «Ninguna» si la corrida no trae la clave `externo`
    (las de hoy) o si todas las etapas son locales; queda en el bloque «Estado»."""
    a, b, c = three
    open_matrix()
    declaration = requirement(procedure, "declaración jurada")
    add_external_run(operator_user, procedure, a, {declaration: "cumple"},
                     external_key({"matriz": "local", "verificador": "externo"}))
    add_run(operator_user, procedure, b, {declaration: "cumple"})
    add_external_run(operator_user, procedure, c, {declaration: "cumple"},
                     external_key({"matriz": "local", "verificador": "local"}))
    log_in(client, operator_user)
    pages = {}
    for offer in (a, b, c):
        response = client.get(
            reverse("expedientes:s4_par", args=[procedure.pk, offer.pk, declaration.pk]))
        assert response.status_code == 200
        pages[offer] = response.content.decode()
    assert VERIFIER_LINE in pages[a] and NONE_LINE not in pages[a]
    assert NONE_LINE in pages[b] and VERIFIER_LINE not in pages[b]
    assert NONE_LINE in pages[c]
    assert pages[a].count("Etapas fuera del equipo") == 1
    assert pages[a].index("<h3>Estado</h3>") < pages[a].index(VERIFIER_LINE) \
        < pages[a].index("Lo que exige el pliego")
