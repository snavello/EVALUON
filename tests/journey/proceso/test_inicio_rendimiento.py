"""Rendimiento del inicio (REQ-150, requisito no funcional; ADR-0079; T-357): con 20
procedimientos abiertos (copias del caso chico) la lista tarda 2 s o menos (mediana de 5).
Material inventado (P4)."""

import statistics
import time

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from tests.journey.proceso.test_inicio import RAIZ, copias, detalles
from tests.journey.proceso.test_portada import entrar

pytestmark = pytest.mark.django_db

PRESUPUESTO = 2.0


def test_req150_veinte_abiertos_en_dos_segundos(client, evaluator_user, expected, fake_ai,
                                                capsys):
    """REQ-150: mediana de 5 cargas con 20 abiertos ≤ 2 s; se informa el número de consultas."""
    copias(evaluator_user, expected, 20)
    entrar(client, evaluator_user)
    tiempos = []
    for _ in range(5):
        with CaptureQueriesContext(connection) as consultas:
            inicio = time.perf_counter()
            html = client.get(RAIZ).content.decode()
            tiempos.append(time.perf_counter() - inicio)
        assert len(detalles(html)) == 20
    with capsys.disabled():
        print(f"\n[inicio, 20 abiertos] mediana {statistics.median(tiempos):.2f} s "
              f"(tiempos {[round(t, 2) for t in tiempos]}), {len(consultas)} consultas")
    assert statistics.median(tiempos) <= PRESUPUESTO


def test_req150_costo_de_un_procedimiento_con_varios_pasos_en_curso(client, caso_varios_en_curso,
                                                                    capsys):
    """Dato para el ADR-0079 (sin tope): lo que cuesta el inicio con un solo procedimiento «varios
    en curso», el caso más pesado de los tres."""
    entrar(client, caso_varios_en_curso.user)
    client.get(RAIZ)
    with CaptureQueriesContext(connection) as consultas:
        inicio = time.perf_counter()
        client.get(RAIZ)
        duracion = time.perf_counter() - inicio
    with capsys.disabled():
        print(f"\n[inicio, 1 varios en curso] {duracion:.2f} s, {len(consultas)} consultas")
