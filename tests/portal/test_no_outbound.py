"""Ningún código fuera de `portal/` abre conexiones salientes (T-138; ADR-0031).

`app` está en la red `web` (un bridge con salida, necesario para publicar el puerto), así
que su garantía de no salir a internet es de código: en `evaluon/`, fuera de
`evaluon/portal/`, nada importa un cliente de red. La única excepción es el cliente de los
servicios de IA (`evaluon/ai/__init__.py`), que habla con los servicios internos
(`generation`, `embeddings`, `reranker`) por la red `internal`, y el cliente de la API
externa (`evaluon/ai/external/client.py`, T-289; ADR-0066), que solo conecta a su anfitrión
fijo por HTTPS y solo si el uso externo está habilitado.
"""

import ast
from pathlib import Path

from django.conf import settings

EVALUON = Path(settings.BASE_DIR) / "evaluon"

# Módulos que abren conexiones (se mira el módulo y sus submódulos).
NETWORK_MODULES = {
    "urllib.request", "urllib3", "requests", "http.client", "httpx", "aiohttp", "socket",
    "ftplib", "smtplib", "poplib", "imaplib", "telnetlib", "websocket", "websockets",
}

# Clientes ya existentes hacia servicios internos, y el de la API externa (exactamente este
# archivo; el resto de `evaluon/ai/external/` no importa ningún módulo de red).
EXTERNAL_CLIENT = EVALUON / "ai" / "external" / "client.py"
ALLOWED = {EVALUON / "ai" / "__init__.py", EXTERNAL_CLIENT}


def imported_modules(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            yield node.module
            for alias in node.names:
                yield f"{node.module}.{alias.name}"


def is_network(module):
    return any(module == name or module.startswith(name + ".") for name in NETWORK_MODULES)


def offenders():
    found = []
    for path in sorted(EVALUON.rglob("*.py")):
        if (EVALUON / "portal") in path.parents or path in ALLOWED:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        found += [f"{path.relative_to(EVALUON)}: {m}" for m in set(imported_modules(tree))
                  if is_network(m)]
    return found


def test_only_portal_and_the_ai_clients_import_network_modules():
    """REQ-045, REQ-122, P4: fuera de `evaluon/portal/` no hay imports de `urllib.request`,
    `requests`, `http.client`, `socket` ni similares, salvo el cliente de los servicios
    internos de IA y el de la API externa."""
    assert offenders() == []


def test_the_external_client_is_the_only_allowed_addition():
    """REQ-122: lo permitido es exactamente el cliente de IA de hoy y
    `evaluon/ai/external/client.py`; el resto del paquete externo (`payload.py` y lo que
    siga) no importa ningún módulo de red."""
    assert ALLOWED == {EVALUON / "ai" / "__init__.py", EVALUON / "ai" / "external" / "client.py"}
    assert EXTERNAL_CLIENT.is_file()
    for path in sorted((EVALUON / "ai" / "external").rglob("*.py")):
        if path == EXTERNAL_CLIENT:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        assert [m for m in imported_modules(tree) if is_network(m)] == [], path.name


def external_imports(tree):
    """Imports que traen `evaluon.ai.external` (absolutos o relativos)."""
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found += [a.name for a in node.names if a.name.startswith("evaluon.ai.external")]
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names = [f"{module}.{a.name}" for a in node.names]
            if (module.startswith("evaluon.ai.external") or "ai.external" in module
                    or any(n.strip(".").endswith("ai.external") for n in names)
                    or (module.endswith("ai") or module == "") and any(
                        a.name == "external" for a in node.names)):
                found.append(f"{'.' * node.level}{module}")
    return found


def test_the_portal_does_not_import_the_external_client():
    """REQ-122, P4 (O-288-4): `portal_worker` es el único servicio con `egress` y recibe las
    mismas variables que `app`; el código del Portal no importa nada de `evaluon.ai.external`,
    de modo que no puede llamar a la API externa."""
    found = []
    for path in sorted((EVALUON / "portal").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        found += [f"{path.relative_to(EVALUON)}: {m}" for m in external_imports(tree)]
    assert found == []


def test_the_external_import_detector_sees_every_form():
    """REQ-122: el detector de arriba encuentra las formas de importar el cliente externo."""
    for source in ("import evaluon.ai.external.client",
                   "from evaluon.ai.external import client",
                   "from evaluon.ai.external.client import send_message",
                   "from evaluon.ai import external",
                   "from ..ai.external import client",
                   "from ..ai import external"):
        assert external_imports(ast.parse(source)), source
    for source in ("from evaluon.ai import generation", "import urllib.parse",
                   "from . import client"):
        assert external_imports(ast.parse(source)) == [], source


def test_the_scan_sees_the_known_clients():
    """El detector funciona: encuentra los imports del cliente de IA y del cliente del
    Portal."""
    ai = ast.parse(Path(EVALUON / "ai" / "__init__.py").read_text(encoding="utf-8"))
    assert any(is_network(m) for m in imported_modules(ai))
    portal = ast.parse((EVALUON / "portal" / "client.py").read_text(encoding="utf-8"))
    assert "http.client" in set(imported_modules(portal))
    assert is_network("socket") and not is_network("urllib.parse")
