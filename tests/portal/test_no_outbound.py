"""Ningún código fuera de `portal/` abre conexiones salientes (T-138; ADR-0031).

`app` está en la red `web` (un bridge con salida, necesario para publicar el puerto), así
que su garantía de no salir a internet es de código: en `evaluon/`, fuera de
`evaluon/portal/`, nada importa un cliente de red. La única excepción es el cliente de los
servicios de IA (`evaluon/ai/__init__.py`), que habla con los servicios internos
(`generation`, `embeddings`, `reranker`) por la red `internal`.
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

# Clientes ya existentes hacia servicios internos.
ALLOWED = {EVALUON / "ai" / "__init__.py"}


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


def test_only_portal_and_the_ai_client_import_network_modules():
    """REQ-045, P4: fuera de `evaluon/portal/` no hay imports de `urllib.request`,
    `requests`, `http.client`, `socket` ni similares, salvo el cliente de los servicios
    internos de IA."""
    assert offenders() == []


def test_the_scan_sees_the_known_clients():
    """El detector funciona: encuentra los imports del cliente de IA y del cliente del
    Portal."""
    ai = ast.parse(Path(EVALUON / "ai" / "__init__.py").read_text(encoding="utf-8"))
    assert any(is_network(m) for m in imported_modules(ai))
    portal = ast.parse((EVALUON / "portal" / "client.py").read_text(encoding="utf-8"))
    assert "http.client" in set(imported_modules(portal))
    assert is_network("socket") and not is_network("urllib.parse")
