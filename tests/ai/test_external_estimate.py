"""El estimado del libro, calibrado con las cifras de la medición T-293 (T-294; REQ-122, REQ-123;
D-293-5; ADR-0068, punto 4; plan 016, «Costo y tope»).

T-293 midió con el proveedor real que la regla de 2,5 caracteres por token subestimaba los tokens de
entrada 1,17 a 1,27 veces y que el estimado de un caso salía 1,6 a 2,2 veces el costo real: reservaba
`max_tokens` de salida en cada pedido y cobraba la entrada sin distinguir escritura y lectura de la
caché. Estas pruebas fijan las cifras de esa medición (caracteres y tokens de cada pedido, y el costo
real de cada caso) y comprueban que el estimado nuevo:

- no queda por debajo de los tokens reales de ningún pedido (y a menos de 1,15 veces);
- queda entre 1 y 1,5 veces el costo real de cada caso;
- cobra aparte la escritura y la lectura de la caché y la salida esperada;
- no cuenta dos veces un lote en vuelo cuyo pedido ya tiene su hecho `ok`, ni contra el tope del
  caso ni contra el del mes.

Sin red. Los textos son sintéticos (P4): solo importan los largos.
"""

from decimal import Decimal

import pytest
from django.core.exceptions import ImproperlyConfigured

from evaluon.ai.external import ledger
from evaluon.ai.external import guard
from tests.ai.test_external_guard import (  # noqa: F401 - fixtures y ayudas de la puerta
    MEASUREMENT,
    ask,
    case,
    debt_in_catalog,
    evaluator_user,
    expected,
    external_requests,
    matrix,
    operator_user,
    procedure,
)
from tests.ai.test_external_ledger import economic, in_flight_events, technical
from tests.conftest import external_payload

pytestmark = pytest.mark.django_db

# Cifras de T-293 (solo números): caracteres del sistema (el pliego completo con la instrucción) y
# de los mensajes de los tres pedidos de cada caso (dos de extracción y uno de completitud y
# filtro), tokens de entrada que informó el proveedor en cada uno (entrada, escritura y lectura de
# caché) y el costo real del caso en USD (precios de lista del 2026-10-15, en lotes).
T293 = {
    "00": {"system": 105_343, "messages": (570, 661, 13_256),
           "tokens": (49_817, 49_817, 55_563), "cost": Decimal("0.274907")},
    "02": {"system": 159_414, "messages": (664, 751, 14_023),
           "tokens": (81_327, 81_324, 87_277), "cost": Decimal("0.413238")},
    "06": {"system": 121_517, "messages": (593, 685, 12_158),
           "tokens": (60_353, 60_353, 65_644), "cost": Decimal("0.314380")},
}


def other(case, number):
    """Un pedido de texto propio (no se reutiliza por huella con los demás de la medición)."""
    return ask(case, [guard.instruction(f"Pedido distinto número {number}, de texto propio.")],
               custom_id=f"pedido-{number}")


def payload_of(case_id, index, **overrides):
    """El pedido número `index` (0 y 1: extracción; 2: completitud) del caso de T-293, con textos
    sintéticos del largo medido."""
    figures = T293[case_id]
    return external_payload(
        system="s" * figures["system"],
        messages=[{"role": "user", "content": "m" * figures["messages"][index]}],
        custom_id=f"matriz-{case_id}-{index}", max_tokens=32_000,
        stage="matriz_completitud_filtro" if index == 2 else "matriz_extraccion",
        cache_system_ttl="1h", **overrides)


def chars_of(payload):
    return len(payload.system) + sum(len(text) for _, text in payload.messages)


@pytest.mark.parametrize("case_id", sorted(T293))
def test_d_293_5_the_token_estimate_is_never_below_the_real_tokens(case_id):
    """REQ-122, D-293-5: con la regla vieja (2,5 caracteres por token) los tokens de entrada de cada
    pedido de T-293 salían 0,79 a 0,85 de los reales; con la calibrada ninguno queda por debajo ni
    pasa de 1,15 veces."""
    for index, real in enumerate(T293[case_id]["tokens"]):
        estimated = ledger.estimate_tokens(chars_of(payload_of(case_id, index)))
        assert real <= estimated <= real * Decimal("1.15"), (case_id, index, estimated, real)


@pytest.mark.parametrize("case_id", sorted(T293))
def test_d_293_5_the_case_estimate_is_close_to_the_real_cost_and_never_below(case_id):
    """REQ-122, D-293-5: el estimado de los pedidos de un caso (la extracción en un lote y la
    completitud en otro, como los manda la etapa) queda entre 1 y 1,5 veces su costo real en
    T-293 (con la regla vieja: 1,6 a 2,2 veces)."""
    figures = T293[case_id]
    extraction = ledger.estimate_batch([payload_of(case_id, 0), payload_of(case_id, 1)], "lotes")
    completion = ledger.estimate_batch([payload_of(case_id, 2)], "lotes")
    estimated = sum(extraction, Decimal(0)) + sum(completion, Decimal(0))

    assert figures["cost"] <= estimated <= figures["cost"] * Decimal("1.5"), (case_id, estimated)


def test_d_293_5_cache_write_read_and_output_are_priced_apart():
    """REQ-122, D-293-5: el primer pedido de un sistema con caché paga la escritura (2 veces la
    entrada, la única tarifa de la tabla) y los que comparten su sistema pagan la lectura (0,05); la
    salida esperada se cobra aparte y no pasa de `max_tokens`; sin caché, la entrada va al precio
    entero."""
    first, second = payload_of("00", 0), payload_of("00", 1)
    tokens = ledger.estimate_tokens(len(first.system))
    million = Decimal(1_000_000)
    salida = ledger.OUTPUT_TOKENS_ESTIMATE * Decimal(10) / 2 / million  # lotes: a la mitad

    only = ledger.estimate_batch([first], "lotes")[0]
    shared = ledger.estimate_batch([first, second], "lotes")
    message = ledger.estimate_tokens(chars_of(first) - len(first.system)) * Decimal(2) / 2 / million
    system_write = tokens * Decimal(2) * Decimal(2) / 2 / million
    system_read = tokens * Decimal(2) * Decimal("0.05") / 2 / million

    assert only == ledger._round(system_write + message + salida)
    assert shared[0] == only
    assert shared[1] < only / 2
    assert shared[1] == ledger._round(system_read + ledger.estimate_tokens(
        chars_of(second) - len(second.system)) * Decimal(2) / 2 / million + salida)
    # Sin caché del sistema, todo va a precio de entrada.
    plain = external_payload(system="s" * len(first.system), cache_system_ttl=None,
                             messages=[{"role": "user", "content": "m" * 570}], max_tokens=32_000)
    assert ledger.estimate_batch([plain], "lotes")[0] == ledger._round(
        ledger.estimate_tokens(chars_of(plain)) * Decimal(2) / 2 / million + salida)
    # La salida esperada no pasa de `max_tokens`.
    small = external_payload(system="s", messages=[{"role": "user", "content": "m"}],
                             max_tokens=100, cache_system_ttl=None)
    assert ledger.estimate_batch([small], "directo")[0] < Decimal("0.0011")
    # El estimado de un pedido suelto es el del lote de un pedido.
    assert ledger.estimate(first, "lotes") == only


def test_d_293_5_a_request_of_a_model_without_a_price_has_no_estimate():
    """REQ-122: un modelo sin precio en `EXTERNAL_PRICES` no tiene estimado (el libro lo bloquea
    con `sin_precio`), también dentro de un lote."""
    unknown = external_payload(model="modelo-sin-precio")

    assert ledger.estimate(unknown, "lotes") is None
    assert ledger.estimate_batch([payload_of("00", 0), unknown], "lotes")[1] is None


def test_d_293_5_a_price_factor_that_is_not_positive_is_a_configuration_error(settings):
    """REQ-122 (O-288-2): el estimado cobra con los factores de la tabla; uno que no es un número
    finito y positivo no se usa."""
    settings.EXTERNAL_PRICES = {**settings.EXTERNAL_PRICES, "cache_escritura_1h": Decimal("0")}

    with pytest.raises(ImproperlyConfigured, match="cache_escritura_1h"):
        ledger.estimate_batch([payload_of("00", 0)], "lotes")


# --- Un lote en vuelo con sus pedidos ya registrados no cuenta dos veces ------------------------------


def test_d_293_5_a_batch_with_its_requests_recorded_counts_once_against_the_case_and_the_month(
        case, fake_external):  # noqa: F811
    """REQ-122, D-293-5 (O-291-2): después de un lote queda su hecho `en_vuelo` con el estimado junto
    a los hechos `ok` con el costo real; las sumas del caso, del mes y de la etapa son solo el costo
    real, con dos lotes del mismo caso (extracción y completitud)."""
    fake_external.enable()
    fake_external.respond("ok", usage={"input_tokens": 1000, "output_tokens": 100,
                                       "cache_creation_input_tokens": 5000})
    first = ledger.send([economic(case), technical(case)], measurement=MEASUREMENT)
    second = ledger.send([other(case, 3)], measurement=MEASUREMENT)

    flights = in_flight_events()
    assert len(flights) == 2 and all(f.detail["costo_usd"] > 0 for f in flights)
    real = first.cost_usd + second.cost_usd
    assert real > 0
    assert ledger.spent_case(case.procedure.pk) == real
    assert ledger.spent_month() == real
    assert ledger.spent_stage("verificador", case.procedure.pk, measurement=MEASUREMENT) == real
    assert sum(Decimal(str(e.detail["costo_usd"])) for e in external_requests()
               if e.detail["resultado"] == "ok") == real


def test_d_293_5_the_estimate_of_a_closed_batch_does_not_use_up_the_cap_of_the_next(
        case, fake_external, settings):  # noqa: F811
    """REQ-122, D-293-5: el tope se compara con el costo real gastado más el estimado del lote por
    mandar. Con el tope del caso apenas por encima de eso, el segundo lote sale aunque el `en_vuelo`
    del primero (que estimaba más que lo real) siga en el registro; si se contara dos veces, el
    segundo quedaría bloqueado por `tope`."""
    fake_external.enable()
    fake_external.respond("ok", usage={"input_tokens": 1000, "output_tokens": 100})
    batch = [economic(case), technical(case)]
    estimate_first = sum(ledger.estimate_batch([i.payload for i in batch], "lotes"), Decimal(0))
    first = ledger.send(batch, measurement=MEASUREMENT)
    nxt = other(case, 3)
    estimate_next = ledger.estimate(nxt.payload, "lotes")
    assert first.cost_usd < estimate_first
    cap = first.cost_usd + estimate_next + Decimal("0.0001")
    assert cap < estimate_first + estimate_next  # contado dos veces, no entraría
    settings.EXTERNAL_CASE_CAP_USD = cap
    settings.EXTERNAL_MONTH_CAP_USD = cap

    second = ledger.send([nxt], measurement=MEASUREMENT)

    assert second.answers["pedido-3"].ok, second.answers["pedido-3"].reason
