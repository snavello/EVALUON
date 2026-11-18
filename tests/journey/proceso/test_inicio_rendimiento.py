"""Rendimiento del inicio (REQ-150, requisito no funcional; ADR-0079; T-357, T-361): con 20
procedimientos abiertos «varios en curso» (el caso más pesado) la lista sale enseguida con el
nombre, el número y el vencimiento de cada uno, y los pasos y las acciones de cada procedimiento
llegan por separado (`expedientes/<id>/fila/`). Cada pedido tarda 3 s o menos (decisión del
responsable del 2026-11-18) y, para que una máquina ocupada no dé falsos rojos, el límite firme es
el de consultas, que no depende de la máquina. Material inventado (P4)."""

import statistics
import time

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from tests.journey.proceso.conftest import armar_varios_en_curso
from tests.journey.proceso.test_inicio import RAIZ, copias, detalles
from tests.journey.proceso.test_portada import entrar

pytestmark = pytest.mark.django_db

PRESUPUESTO = 3.0  # segundos, por pedido (decisión del responsable del 2026-11-18, antes 2.0)
CONSULTAS_LISTA_POR_PROCEDIMIENTO = 8  # medido: 4,4 (la lista no calcula pasos ni acciones)
CONSULTAS_FILA = 200  # medido: unas 110 por procedimiento «varios en curso»


def test_req150_veinte_abiertos_lista_enseguida_y_cada_fila_aparte(
        client, evaluator_user, expected, fake_ai, capsys):
    """REQ-150: la respuesta inicial con 20 abiertos y cada fila por separado, ≤ 3 s; se informan
    tiempos y consultas. La lista ya trae los 20, ordenados, con un enlace a cada uno."""
    hechos = copias(evaluator_user, expected, 20)
    for procedure in hechos:
        armar_varios_en_curso(procedure, evaluator_user)
    entrar(client, evaluator_user)
    tiempos = []
    for _ in range(5):
        with CaptureQueriesContext(connection) as consultas:
            inicio = time.perf_counter()
            html = client.get(RAIZ).content.decode()
            tiempos.append(time.perf_counter() - inicio)
        assert len(detalles(html)) == 20
    assert all(reverse("expedientes:portada", args=[p.pk]) in html for p in hechos)
    assert len(consultas) <= CONSULTAS_LISTA_POR_PROCEDIMIENTO * 20
    parciales, consultas_fila = [], []
    for procedure in hechos:
        with CaptureQueriesContext(connection) as por_fila:
            inicio = time.perf_counter()
            respuesta = client.get(reverse("expedientes:fila", args=[procedure.pk]))
            parciales.append(time.perf_counter() - inicio)
        consultas_fila.append(len(por_fila))
        assert respuesta.status_code == 200
        assert f'data-procedimiento="{procedure.pk}"' in respuesta.content.decode()
    with capsys.disabled():
        print(f"\n[inicio, 20 varios en curso] lista: mediana {statistics.median(tiempos):.2f} s "
              f"(peor {max(tiempos):.2f}), {len(consultas)} consultas; cada fila: mediana "
              f"{statistics.median(parciales):.2f} s (peor {max(parciales):.2f}), "
              f"{max(consultas_fila)} consultas como máximo")
    assert statistics.median(tiempos) <= PRESUPUESTO
    assert statistics.median(parciales) <= PRESUPUESTO
    assert max(consultas_fila) <= CONSULTAS_FILA
