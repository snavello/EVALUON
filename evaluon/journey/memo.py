"""Memoria por pedido de lo que la pantalla de un procedimiento calcula más de una vez (T-221).

`matrix_page` (la definición única del estado de cada par, ADR-0039) es cara y la pedían, en la
misma carga, la etapa de la evaluación, tres temas del Informe y la Propuesta, y el contexto de
cada uno. Dentro de un `with scope():` se calcula una sola vez por usuario, procedimiento y
canal; fuera de uno no guarda nada (cada llamada calcula, como antes). El alcance dura lo que
dura el pedido de lectura (`sections_for` y las vistas GET de `portada`): nunca entre pedidos, así
que no hay datos viejos. Solo lee; no decide nada (P3)."""

from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps

from evaluon.assessment.services import matrix as matrix_service
from evaluon.audit.models import Channel

_active: ContextVar = ContextVar("journey_memo", default=None)


@contextmanager
def scope():
    """Abre el alcance de la memoria; si ya hay uno abierto, usa ese."""
    if _active.get() is not None:
        yield
        return
    token = _active.set({})
    try:
        yield
    finally:
        _active.reset(token)


def scoped(view):
    """Decorador: toda la vista (cálculo y dibujo) corre dentro de un alcance."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        with scope():
            return view(*args, **kwargs)
    return wrapper


def matrix_page(user, procedure_id, *, channel=Channel.SCREEN):
    """`matrix_service.matrix_page`, calculada una vez por alcance. La primera llamada hace la
    comprobación de rol y su registro; si lanza, no se guarda nada."""
    memo = _active.get()
    if memo is None:
        return matrix_service.matrix_page(user, procedure_id, channel=channel)
    key = ("matrix_page", getattr(user, "pk", None), procedure_id, channel)
    if key not in memo:
        memo[key] = matrix_service.matrix_page(user, procedure_id, channel=channel)
    return memo[key]


def once(key, compute):
    """`compute()` una vez por alcance y clave; fuera de un alcance calcula siempre. Para lo que
    el estado de una sección y el contexto de su tema piden en la misma carga."""
    memo = _active.get()
    if memo is None:
        return compute()
    key = ("once", key)
    if key not in memo:
        memo[key] = compute()
    return memo[key]
