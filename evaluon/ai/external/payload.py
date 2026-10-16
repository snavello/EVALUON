"""`ExternalPayload`: el único pedido que acepta el cliente de la API externa (ADR-0066 y
ADR-0067; plan 016, "Puerta de filtrado").

El filtrado de lo reservado ocurre en `guard.py` (T-290), y solo ahí: es el único módulo que
construye un `ExternalPayload`, con `ExternalPayload.from_guard(...)`. El cliente rechaza todo
lo que no sea uno. El constructor directo (`ExternalPayload(...)`) falla: un pedido armado a
mano, sin pasar por la puerta, no puede salir. `tests/ai/test_external_client.py` comprueba
que ningún otro archivo de `evaluon/` llama a `from_guard`.

El pedido es inmutable: todo lo que lleva son textos, números y tuplas. El cuerpo del mensaje
se arma con `to_params()` (una copia nueva cada vez) y su huella sale de él.

No importa ningún módulo de red.
"""

import hashlib
import json
from dataclasses import dataclass, field

# El nombre de la etapa de un pedido empieza con una etapa de la configuración
# (EXTERNAL_STAGE_NAMES): `matriz_extraccion` es de `matriz`, `verificador` es de `verificador`.
THINKING_LEVELS = ("off", "adaptive", "between_tools")
ROLES = ("user", "assistant")
MAX_CUSTOM_ID = 64

# Marca con la que `from_guard` identifica su propio llamado. No es una defensa contra código
# malicioso: impide armar un pedido por descuido sin pasar por la puerta.
_ISSUED_BY_GUARD = object()


def stage_group(stage):
    """Etapa de la configuración (`matriz`, `verificador`) a la que pertenece `stage`."""
    return str(stage).split("_", 1)[0]


def canonical_json(value):
    """JSON canónico (claves ordenadas, sin espacios, sin escapar el castellano)."""
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _text(name, value, *, allow_empty=False):
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise ValueError(f"ExternalPayload: {name} tiene que ser un texto no vacío.")
    return value


@dataclass(frozen=True)
class ExternalPayload:
    """Un pedido a la API externa, ya filtrado.

    Campos del pedido: `stage` (nombre de la etapa, p. ej. `matriz_extraccion`), `model`,
    `effort` (o `None` para el del proveedor), `thinking` (`off`, `adaptive` o
    `between_tools`), `max_tokens`, `output_schema` (JSON canónico del esquema de salida, o
    `None`), `system`, `messages` (tupla de pares `(rol, texto)`), `cache_system_ttl` (`1h`,
    `5m` o `None` si no se usa caché del prefijo) y `custom_id` (identifica el pedido dentro
    de un lote).

    Campos que el registro necesita (ADR-0068, sin efecto en el pedido): `procedure_id`,
    `offer_id`, `requirement_id`, `run_kind`, `run_id`, y la instrucción y las definiciones
    que la acompañan (`instruction_name`, `instruction_version`, `instruction_sha256`,
    `definitions_version`, `definitions_sha256`).
    """

    stage: str
    model: str
    max_tokens: int
    system: str
    messages: tuple
    custom_id: str
    effort: str | None = None
    thinking: str = "off"
    output_schema: str | None = None
    cache_system_ttl: str | None = "1h"
    procedure_id: int | str | None = None
    offer_id: int | str | None = None
    requirement_id: int | str | None = None
    run_kind: str | None = None
    run_id: int | str | None = None
    instruction_name: str = ""
    instruction_version: str = ""
    instruction_sha256: str = ""
    definitions_version: str = ""
    definitions_sha256: str = ""
    issued_by: object = field(default=None, repr=False, compare=False)

    def __post_init__(self):
        if self.issued_by is not _ISSUED_BY_GUARD:
            raise TypeError(
                "ExternalPayload solo se construye con ExternalPayload.from_guard(), que "
                "llama la puerta de filtrado (evaluon/ai/external/guard.py).")

    @classmethod
    def from_guard(cls, *, stage, model, max_tokens, system, messages, custom_id,
                   effort=None, thinking="off", output_schema=None, cache_system_ttl="1h",
                   **ids):
        """Construye un pedido validado. Lo llama `guard.py` y ningún otro módulo.

        `messages` es una lista de `{"role": ..., "content": texto}` (o de pares
        `(rol, texto)`); `output_schema`, un esquema JSON (dict) o `None`. Un dato inválido
        lanza `ValueError` o `TypeError`; no se corrige nada.
        """
        _text("stage", stage)
        _text("model", model)
        _text("custom_id", custom_id)
        if len(custom_id) > MAX_CUSTOM_ID:
            raise ValueError(f"ExternalPayload: custom_id pasa de {MAX_CUSTOM_ID} caracteres.")
        if isinstance(max_tokens, bool) or not isinstance(max_tokens, int) or max_tokens <= 0:
            raise ValueError("ExternalPayload: max_tokens tiene que ser un entero positivo.")
        _text("system", system, allow_empty=True)
        if effort is not None:
            _text("effort", effort)
        if thinking not in THINKING_LEVELS:
            raise ValueError(f"ExternalPayload: thinking tiene que ser uno de {THINKING_LEVELS}.")
        if cache_system_ttl is not None:
            _text("cache_system_ttl", cache_system_ttl)
        pairs = []
        for message in messages:
            role, content = ((message["role"], message["content"])
                             if isinstance(message, dict) else tuple(message))
            if role not in ROLES:
                raise ValueError(f"ExternalPayload: el rol {role!r} no es uno de {ROLES}.")
            pairs.append((role, _text("el contenido de un mensaje", content)))
        if not pairs:
            raise ValueError("ExternalPayload: hace falta al menos un mensaje.")
        schema_text = None
        if output_schema is not None:
            if not isinstance(output_schema, dict):
                raise ValueError("ExternalPayload: output_schema tiene que ser un esquema JSON.")
            schema_text = canonical_json(output_schema)
        known = {"procedure_id", "offer_id", "requirement_id", "run_kind", "run_id",
                 "instruction_name", "instruction_version", "instruction_sha256",
                 "definitions_version", "definitions_sha256"}
        unknown = set(ids) - known
        if unknown:
            raise TypeError(f"ExternalPayload: campos desconocidos {sorted(unknown)}.")
        return cls(stage=stage, model=model, max_tokens=max_tokens, system=system,
                   messages=tuple(pairs), custom_id=custom_id, effort=effort,
                   thinking=thinking, output_schema=schema_text,
                   cache_system_ttl=cache_system_ttl, issued_by=_ISSUED_BY_GUARD, **ids)

    @property
    def stage_group(self):
        """La etapa de la configuración (`matriz`, `verificador`) de este pedido."""
        return stage_group(self.stage)

    def to_params(self):
        """El cuerpo de `POST /v1/messages` (y los `params` de un pedido de lote): una copia
        nueva cada vez. Solo lleva los campos que el pedido fija; el resto lo decide el
        proveedor."""
        params = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": [{"role": role, "content": text} for role, text in self.messages],
        }
        if self.system:
            if self.cache_system_ttl:
                params["system"] = [{
                    "type": "text", "text": self.system,
                    "cache_control": {"type": "ephemeral", "ttl": self.cache_system_ttl},
                }]
            else:
                params["system"] = self.system
        output_config = {}
        if self.effort:
            output_config["effort"] = self.effort
        if self.output_schema:
            output_config["format"] = {"type": "json_schema",
                                       "schema": json.loads(self.output_schema)}
        if output_config:
            params["output_config"] = output_config
        if self.thinking != "off":
            params["thinking"] = {"type": self.thinking}
        return params

    @property
    def request_sha256(self):
        """Huella del pedido: SHA-256 de su cuerpo canónico (modelo, parámetros y texto). No
        incluye el `custom_id` ni los identificadores del registro."""
        return hashlib.sha256(canonical_json(self.to_params()).encode("utf-8")).hexdigest()
