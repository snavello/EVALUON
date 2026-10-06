"""Medida de tamaños de las ofertas (plan 004, "Qué se lee y cómo se agrupa"; ADR-0037;
T-148).

Para cada oferta: páginas, tokens por documento y por página con el tokenizador del modelo
(`generation.count_tokens`), los documentos de texto idéntico (se cuentan una vez) y cuántos
grupos salen con `ASSESSMENT_GROUP_TOKENS`, en el orden de carga. Es la medida con la que se
confirma la estimación del plan y el contexto del motor de lotes; T-150 reutiliza el armado de
texto por página y el empaquetado (`render_page`, `pack`, `windows`).

Un documento es su última lectura. Una página figura `--- página k ---` con su texto (los
pasajes de la página, que nunca la cruzan) o `--- página k: no se pudo leer ---` si la lectura
la dio por ilegible.

No guarda nada en la base ni en el repositorio: devuelve diccionarios. Los números por
documento los guarda el comando fuera del repositorio.
"""

import json
import urllib.error
import urllib.request

from django.conf import settings

from evaluon.ai import generation

# Estados del informe de lectura que marcan una página como no leída.
UNREAD_KEYS = ("unread",)


def document_pages(reading):
    """Las páginas de una lectura: `[{"page": k, "text": str, "readable": bool}]`, de la 1
    a la última. El texto de una página es el de sus pasajes, en orden."""
    report = reading.report or {}
    unread = {entry["page"] for key in UNREAD_KEYS for entry in report.get(key, [])
              if isinstance(entry, dict) and "page" in entry}
    by_page = {}
    for passage in reading.passages.order_by("order"):
        by_page.setdefault(passage.page, []).append(passage.text)
    total = max([report.get("pages", 0), *by_page, *unread], default=0)
    return [{"page": number, "text": "\n".join(by_page.get(number, [])),
             "readable": number not in unread}
            for number in range(1, total + 1)]


def render_page(page):
    """El texto de una página como lo lee el modelo."""
    if not page["readable"]:
        return f"--- página {page['page']}: no se pudo leer ---"
    return f"--- página {page['page']} ---\n{page['text']}"


def render_header(document):
    """Encabezado de un documento en el pedido: título y archivo."""
    return f"Documento: {document.title}\nArchivo: {document.file_name}"


def windows(page_tokens, budget):
    """Parte un documento mayor que `budget` en ventanas de páginas consecutivas con una
    página de solape. Devuelve listas de índices de página (desde 0). Una página que por sí
    sola supera el presupuesto queda en una ventana propia."""
    result, start, count = [], 0, len(page_tokens)
    while start < count:
        end, used = start, 0
        while end < count and (end == start or used + page_tokens[end] <= budget):
            used += page_tokens[end]
            end += 1
        result.append(list(range(start, end)))
        if end >= count:
            break
        start = end - 1 if end - 1 > start else end
    return result


def pack(items, budget):
    """Empaqueta en grupos, en el orden dado, hasta `budget` tokens. Cada item es un
    diccionario con `tokens`; un item mayor que el presupuesto queda solo en su grupo.
    Devuelve una lista de grupos (listas de items)."""
    groups, current, used = [], [], 0
    for item in items:
        if current and used + item["tokens"] > budget:
            groups.append(current)
            current, used = [], 0
        current.append(item)
        used += item["tokens"]
    if current:
        groups.append(current)
    return groups


def measure_document(document, count):
    """Medida de un documento con su última lectura; `None` en `reading` si no tiene."""
    reading = document.readings.order_by("-sequence").first()
    entry = {"document": document.pk, "title": document.title, "file": document.file_name,
             "kind": document.kind, "reading": None, "sha256": "", "pages": 0,
             "unread_pages": 0, "tokens": 0, "page_tokens": [], "copy_of": None}
    if reading is None:
        return entry
    pages = document_pages(reading)
    page_tokens = [count(render_page(page)) for page in pages]
    entry.update(
        reading=reading.pk, sha256=reading.canonical_sha256, pages=len(pages),
        unread_pages=sum(1 for page in pages if not page["readable"]),
        page_tokens=page_tokens, tokens=count(render_header(document)) + sum(page_tokens))
    return entry


def measure_offer(offer, count=None, budget=None):
    """Medida de una oferta: sus documentos (los de texto idéntico, una vez), el total de
    páginas y tokens, y cuántos grupos salen con `budget` en el orden de carga. Un documento
    mayor que `budget` se parte en ventanas y cada ventana es un item."""
    count = count or generation.count_tokens
    budget = budget or settings.ASSESSMENT_GROUP_TOKENS
    documents, first_seen = [], {}
    for document in offer.documents.order_by("pk"):
        entry = measure_document(document, count)
        if entry["sha256"] in first_seen:
            entry["copy_of"] = first_seen[entry["sha256"]]
        elif entry["sha256"]:
            first_seen[entry["sha256"]] = entry["document"]
        documents.append(entry)

    items, windowed = [], []
    for entry in documents:
        if entry["copy_of"] is not None or entry["reading"] is None:
            continue
        if entry["tokens"] <= budget:
            items.append({"document": entry["document"], "tokens": entry["tokens"]})
            continue
        parts = windows(entry["page_tokens"], budget)
        windowed.append({"document": entry["document"], "windows": len(parts)})
        for part in parts:
            items.append({"document": entry["document"], "pages": [part[0] + 1, part[-1] + 1],
                          "tokens": sum(entry["page_tokens"][i] for i in part)})
    groups = pack(items, budget)

    counted = [entry for entry in documents if entry["copy_of"] is None]
    return {
        "offer": offer.pk,
        "documents": documents,
        "documents_count": len(documents),
        "copies": sum(1 for entry in documents if entry["copy_of"] is not None),
        "without_reading": sum(1 for entry in documents if entry["reading"] is None),
        "pages": sum(entry["pages"] for entry in counted),
        "unread_pages": sum(entry["unread_pages"] for entry in counted),
        "tokens": sum(entry["tokens"] for entry in counted),
        "tokens_with_copies": sum(entry["tokens"] for entry in documents),
        "largest_document_tokens": max((entry["tokens"] for entry in counted), default=0),
        "budget": budget,
        "windowed": windowed,
        "groups": len(groups),
        "group_tokens": [sum(item["tokens"] for item in group) for group in groups],
    }


def engine_context(base_url=None, timeout=10):
    """Contexto (`n_ctx`) con que arrancó el servidor del motor de lotes, según
    `GET /props`; `None` si no responde. Es el valor real, el que cuenta para la memoria
    de video y el que se registra con cada evaluación (P6)."""
    url = (base_url or settings.GENERATION_BATCH_URL).rstrip("/") + "/props"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310
            data = json.loads(response.read())
        return int(data["default_generation_settings"]["n_ctx"])
    except (OSError, urllib.error.URLError, ValueError, KeyError, TypeError):
        return None
