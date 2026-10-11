"""La celda de la pestaña Evaluación muestra las condiciones del requisito, una por una, con su dato
y su resultado (REQ-104; plan 015, "Flujo de IA · Evaluación"; T-237). Los resultados se guardan
directo, sin el modelo; todo el material es inventado (P4)."""

import pytest
from django.urls import reverse

from evaluon.assessment import models as am
from evaluon.journey.temas import s4_propuesta
from tests.accounts.test_session import TEST_PASSWORD
from tests.assessment.test_matrix import requirement  # noqa: F401  (ayuda)

pytestmark = pytest.mark.django_db

CONDITIONS = [
    {"condicion": "La cotización se realiza en pesos argentinos", "dato": "ARS",
     "resultado": "cumple", "resultado_modelo": "cumple",
     "cita": {"tipo": "portal", "texto": "Moneda de la oferta: ARS"}},
    {"condicion": "La cotización incluye IVA", "dato": "", "resultado": "no_determinado",
     "resultado_modelo": "cumple", "cita": None},
]


def save_result(user, procedure, offer, requirement_, outcome, facts):
    """Una evaluación de `offer` con un resultado que lleva `facts` (como lo guarda el armado)."""
    version = procedure.matrix_versions.get(number=1)
    request = am.Request.objects.create(
        procedure=procedure, matrix_version=version, offers=[offer.pk], requirements=None,
        cause=am.Cause.MATRIZ, requested_by=user)
    run = am.Run.objects.create(
        request=request, offer=offer, matrix_version=version, number=1,
        channel=am.Channel.SCREEN, documents=[], norms={}, models_used={}, parameters={},
        prompt_versions={})
    return am.Result.objects.create(
        run=run, offer=offer, requirement=requirement_, outcome=outcome,
        doubt="sin_dato" if outcome == "no_determinado" else "",
        exigence=am.Exigence.CONDICION, explanation="Falta el dato de la condición «IVA».",
        facts=facts)


def log_in(client, user):
    assert client.login(username=user.username, password=TEST_PASSWORD)


def test_the_conditions_are_read_from_the_result_facts():
    """REQ-104: cada condición con su ícono, su nombre de resultado, su dato y dónde está su cita;
    sin condiciones (una regla decidió o es anterior a `evaluacion-v6`) no hay lista."""
    views = s4_propuesta.condition_views({"condiciones": CONDITIONS + [
        {"condicion": "Presenta la constancia", "dato": "constancia 0045", "resultado": "no_consta",
         "cita": {"tipo": "oferta", "documento": "Constancia", "pagina": 2, "texto": "x"}}]})
    assert [v["name"] for v in views] == ["Cumple", "No determinado", "No consta"]
    assert views[0]["datum"] == "ARS" and views[0]["where"] == "dato del Portal de Compras"
    assert views[1]["datum"] == "" and views[1]["where"] == ""
    assert views[2]["where"] == "Constancia · página 2"
    assert [v["icon"] for v in views] == ["cumple", "nodet", "nodet"]
    assert s4_propuesta.condition_views({"regla": "portal_cumple"}) == []
    assert s4_propuesta.condition_views(None) == []


def test_the_tab_and_the_pair_page_list_each_condition_with_its_result(
        client, procedure, offer, operator_user):
    """REQ-104: en la pestaña y en el detalle del par se ve cada condición con su dato y su
    resultado, por separado; la que falta dice «sin dato»."""
    row = requirement(procedure, "declaración jurada")
    save_result(operator_user, procedure, offer, row, "no_determinado",
                {"condiciones": CONDITIONS})
    log_in(client, operator_user)
    tab = client.get(reverse("expedientes:evaluacion", args=[procedure.pk])).content.decode()
    detail = client.get(reverse("expedientes:s4_par", args=[procedure.pk, offer.pk, row.pk])
                        ).content.decode()
    for html in (tab, detail):
        assert "Condiciones del requisito" in html
        assert "La cotización se realiza en pesos argentinos" in html
        assert "dato: ARS" in html and "dato del Portal de Compras" in html
        assert "La cotización incluye IVA" in html and "sin dato" in html
        assert html.index("<b>Cumple</b>") < html.index("<b>No determinado</b>")


def test_a_result_without_conditions_shows_no_list(client, procedure, offer, operator_user):
    """REQ-104: un resultado sin condiciones no muestra la lista."""
    row = requirement(procedure, "declaración jurada")
    save_result(operator_user, procedure, offer, row, "cumple", {})
    log_in(client, operator_user)
    html = client.get(reverse("expedientes:evaluacion", args=[procedure.pk])).content.decode()
    assert "Condiciones del requisito" not in html
