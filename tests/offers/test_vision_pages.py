"""Qué páginas de una lectura se leyeron por visión (REQ-053, REQ-104; ADR-0041; O-264-1; plan 015,
T-264). Cuentan solo las que la visión leyó: una página legible que nunca pasó por la visión y una que
la visión intentó y descartó (la página sigue como estaba, no es una transcripción) no cuentan.
Todo se pide de una vez, con una consulta. Material inventado (P4)."""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from evaluon.offers import vision
from tests.journey.temas.test_s4_fundamento_pantallas import vision_reading

pytestmark = pytest.mark.django_db


def test_only_the_pages_the_vision_read_count_in_a_mixed_reading(offer):
    """REQ-053, REQ-104: en una lectura mixta, la página 1 se leyó por visión, la 2 es legible y la 3
    la visión la descartó: solo la 1 cuenta; una lectura sin visión no figura."""
    document = offer.documents.get(file_name="oferta.pdf")
    plain = document.readings.get()
    mixed = vision_reading(document, pages=(1,), discarded=(3,))
    other = vision_reading(offer.documents.get(file_name="constancia.pdf"), pages=(2,))
    found = vision.pages_read_in([mixed.pk, plain.pk, other.pk, None, 0, 10**9])
    assert found == {mixed.pk: {1}, other.pk: {2}}
    assert vision.pages_read_in([]) == {} and vision.pages_read_in([None, 0]) == {}


def test_on_vision_answers_for_every_pair_with_one_query(offer):
    """REQ-100, T-223: de una lista de pares (lectura, página), `on_vision` deja los de las páginas
    leídas por visión con una sola consulta, sea cual sea la cantidad de pares; sin pares, ninguna."""
    document = offer.documents.get(file_name="oferta.pdf")
    plain = document.readings.get()
    mixed = vision_reading(document, pages=(1,), discarded=(3,))
    other = vision_reading(offer.documents.get(file_name="constancia.pdf"), pages=(2,))
    pairs = [(mixed.pk, 1), (mixed.pk, 2), (mixed.pk, 3), (plain.pk, 1), (other.pk, 2),
             (other.pk, 1)]
    with CaptureQueriesContext(connection) as queries:
        assert vision.on_vision(pairs * 10) == {(mixed.pk, 1), (other.pk, 2)}
    assert len(queries) == 1
    with CaptureQueriesContext(connection) as queries:
        assert vision.on_vision([]) == set()
    assert len(queries) == 0
