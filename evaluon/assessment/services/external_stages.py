"""La línea «Etapas fuera del equipo» de la pantalla y de la exportación de la evaluación (REQ-122,
P6; plan 016, "Modelo de datos"; ADR-0068, punto 2; T-300).

Lee la clave `externo` que una corrida guarda en `models_used` (proveedor y modelo), `parameters`
(modo) y `counts` (cantidad de pedidos y gasto), con `etapas` (`{matriz: local|externo,
verificador: local|externo}`) para saber qué etapas salieron del equipo. Cada dato se busca en la
entrada propia de la etapa (`externo["verificador"]["modelo"]`) y, si no está, en el nivel general
de la clave (`externo["modelo"]`). Las corridas de hoy no tienen la clave: dicen «Ninguna». Una
clave con otra forma se lee igual, como «Ninguna»: la línea nunca rompe la pantalla.

No decide nada ni escribe nada: solo cuenta lo que la corrida ya registró.
"""

KEY = "externo"
LABEL = "Etapas fuera del equipo"
NONE = "Ninguna: todo corrió en el equipo"
MISSING = "sin dato"
STAGES = (("matriz", "matriz de requisitos"), ("verificador", "verificador de citas"))


def _block(run, column):
    value = (getattr(run, column, None) or {})
    value = value.get(KEY) if isinstance(value, dict) else None
    return value if isinstance(value, dict) else {}


def _field(run, stage, key, columns):
    """El dato `key` de la etapa: primero en su entrada propia, después en el nivel general."""
    for column in columns:
        block = _block(run, column)
        own = block.get(stage)
        if isinstance(own, dict) and own.get(key) not in (None, ""):
            return own[key]
        if block.get(key) not in (None, "") and not isinstance(block.get(key), dict):
            return block[key]
    return None


def _outside(run):
    """Las etapas de la corrida que corrieron fuera del equipo, con sus datos."""
    stages = _block(run, "models_used").get("etapas")
    if not isinstance(stages, dict):
        return []
    found = []
    for stage, _ in STAGES:
        if stages.get(stage) != "externo":
            continue
        requests = _field(run, stage, "pedidos", ("counts",))
        found.append({
            "stage": stage,
            "provider": _field(run, stage, "proveedor", ("models_used", "parameters")),
            "model": _field(run, stage, "modelo", ("models_used", "parameters")),
            "mode": _field(run, stage, "modo", ("parameters", "models_used")),
            "requests": requests if isinstance(requests, int)
            and not isinstance(requests, bool) else None})
    return found


def line(runs):
    """«Etapas fuera del equipo: …» para las corridas dadas (una en la pantalla de un resultado,
    la última de cada oferta en la exportación). Cada etapa figura una vez por proveedor, modelo
    y modo, con la suma de sus pedidos."""
    grouped = {}
    for run in runs:
        for item in _outside(run):
            key = (item["stage"], item["provider"], item["model"], item["mode"])
            total = grouped.get(key)
            if item["requests"] is not None:
                total = (total or 0) + item["requests"]
            grouped[key] = total
    if not grouped:
        return f"{LABEL}: {NONE}."
    labels = dict(STAGES)
    parts = []
    for (stage, provider, model, mode), requests in sorted(
            grouped.items(), key=lambda entry: [s for s, _ in STAGES].index(entry[0][0])):
        count = MISSING if requests is None else \
            f"{requests} pedido{'' if requests == 1 else 's'}"
        parts.append(f"{labels[stage]} ({provider or MISSING}, {model or MISSING}, "
                     f"modo {mode or MISSING}, {count})")
    return f"{LABEL}: {'; '.join(parts)}."
