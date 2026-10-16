"""Puerta de filtrado de lo reservado (T-290; REQ-121; ADR-0067; plan 016, "Un solo punto de
filtrado de lo reservado").
"""

import copy
import dataclasses
import pickle

import pytest

from evaluon.ai.external import client
from tests.conftest import external_payload


def test_a_replaced_payload_is_rejected():
    """REQ-121 (O-289-4): `dataclasses.replace` sobre un pedido no da un pedido que el cliente
    acepte: no pasó por la puerta."""
    payload = external_payload()
    with pytest.raises(TypeError, match="from_guard"):
        dataclasses.replace(payload, system="Texto colado sin pasar por la puerta.")


@pytest.mark.parametrize("duplicate", [copy.copy, copy.deepcopy, lambda p: pickle.loads(
    pickle.dumps(p))])
def test_a_copied_payload_is_rejected(duplicate):
    """REQ-121 (O-289-4): ni `copy`, ni `deepcopy`, ni `pickle` sacan un pedido nuevo sin la
    puerta."""
    with pytest.raises(TypeError):
        duplicate(external_payload())


def test_a_tampered_payload_is_rejected_by_the_client():
    """REQ-121 (O-289-4): un pedido cambiado por la fuerza después de armado
    (`object.__setattr__`) no pasa la comprobación del cliente."""
    payload = external_payload()
    client._check_payload(payload)
    object.__setattr__(payload, "system", "Texto colado después de la puerta.")
    with pytest.raises(TypeError, match="puerta"):
        client._check_payload(payload)
