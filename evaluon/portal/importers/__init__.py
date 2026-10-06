"""Tipos de ítem que se importan del Portal (plan 012, "Estructura del código"; ADR-0030).

Cada archivo de este paquete es un importador y expone:

- `KIND` (o `KINDS`, si el archivo maneja más de un tipo de ítem): el tipo de ítem;
- `explore(context)`: lee lo que le toca de la exploración y devuelve una lista de `Draft`;
  lo que no puede leer lo anota en `context.anomalies`, sin frenar el resto;
- `load(user, item, confirmation=None, channel=...)`: carga el ítem ya aprobado llamando a
  los servicios de la 003 y la 008; devuelve `(modelo, id)` de lo que creó o asoció, o
  levanta una excepción con el motivo.

Se descubren por nombre de archivo: sumar un tipo es sumar un archivo, sin tocar un
registro común (plan 012, "Paralelismo").
"""

import hashlib
import importlib
import json
import pkgutil
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal


@dataclass
class Draft:
    """Un ítem que un importador propone."""

    kind: str
    key: str
    payload: dict
    damaged_fields: list = field(default_factory=list)
    file: object = None


def jsonable(value):
    """El valor con fechas y decimales pasados a texto, para guardarlo como JSON."""
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


def content_sha256(payload):
    """Huella del contenido propuesto: igual contenido, igual huella."""
    text = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def discover():
    """`{tipo de ítem: módulo}` de los importadores de este paquete."""
    registry = {}
    for info in pkgutil.iter_modules(__path__):
        module = importlib.import_module(f"{__name__}.{info.name}")
        kinds = getattr(module, "KINDS", None) or (
            (module.KIND,) if hasattr(module, "KIND") else ()
        )
        for kind in kinds:
            registry[kind] = module
    return registry
