"""Qué se leyó y dónde, cuando un resultado no tiene cita de la oferta (plan 014, T-228; REQ-089;
P3, P6).

Un resultado sin texto de la oferta que lo respalde dice «Sin texto de la oferta que respalde una
conclusión»; sin más, la Comisión no sabe si el sistema leyó la oferta o no. La corrida guarda
cada pedido al modelo (`Step.documents`: documento y, si fue una ventana, sus páginas) y los
documentos analizados (`Run.documents`: título, páginas y páginas ilegibles). Este módulo arma, con
eso, una frase que dice qué documentos y páginas se leyeron para ese requisito; si la corrida no
guardó nada, lo dice. Solo lee lo registrado: no cambia ningún resultado ni su explicación.
"""

from collections import defaultdict

from evaluon.assessment.models import Purpose, Step

NOTHING = "No quedó registrado qué se leyó."


def _range_text(ranges):
    """`[(1, 2), (2, 3), (5, 5)]` -> «páginas 1 a 3 y 5»."""
    merged = []
    for first, last in sorted(ranges):
        if merged and first <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], last)
        else:
            merged.append([first, last])
    parts = [str(a) if a == b else f"{a} a {b}" for a, b in merged]
    plural = len(merged) > 1 or merged[0][0] != merged[0][1]
    return f"{'páginas' if plural else 'página'} {' y '.join(parts)}"


def _unread(documents):
    found = []
    for entry in documents:
        pages = entry.get("unread_pages") or []
        numbers = [p["page"] if isinstance(p, dict) else p for p in pages]
        if numbers:
            found.append(f"{'página' if len(numbers) == 1 else 'páginas'} "
                         f"{', '.join(str(n) for n in numbers)} de «{entry.get('title', '')}»")
    return found


def note_for(run, steps):
    """La frase de lo leído para un par. `run` es la corrida (con `documents`) y `steps` son los
    `documents` de cada pedido al modelo del par (lista de listas)."""
    record = {entry["document"]: entry for entry in (run.documents or [])
              if isinstance(entry, dict) and "document" in entry}
    read = defaultdict(list)
    for step in steps:
        for entry in step or []:
            if not isinstance(entry, dict) or "document" not in entry:
                continue  # la nota de relevancia del pedido no es un documento
            known = record.get(entry["document"], {})
            pages = entry.get("pages") or ([1, known["pages"]] if known.get("pages") else None)
            read[entry["document"]].append(tuple(pages) if pages else None)
    unread = _unread(record.values())
    tail = f" No se pudieron leer: {'; '.join(unread)}." if unread else ""
    if read:
        shown = []
        for document, ranges in read.items():
            title = record.get(document, {}).get("title", f"documento {document}")
            known = [r for r in ranges if r]
            where = f" ({_range_text(known)})" if known else ""
            shown.append(f"«{title}»{where}")
        return f"Se leyó: {'; '.join(shown)}.{tail}"
    if record:
        shown = []
        for entry in record.values():
            count = entry.get("pages")
            shown.append(f"«{entry.get('title', '')}»" + (f" ({count} página"
                                                         f"{'' if count == 1 else 's'})"
                                                         if count else ""))
        return ("La evaluación de la oferta analizó " + "; ".join(shown)
                + f"; no quedó registrado cuáles se leyeron para este requisito.{tail}")
    return NOTHING


def notes_for(results):
    """`{id del resultado: frase}` de los `results` dados (con su corrida cargada), con una sola
    consulta a los pedidos al modelo."""
    results = list(results)
    if not results:
        return {}
    steps = defaultdict(list)
    for run_id, requirement_id, documents in (
            Step.objects.filter(run_id__in={r.run_id for r in results},
                                requirement_id__in={r.requirement_id for r in results},
                                purpose=Purpose.GRUPO)
            .order_by("pk").values_list("run_id", "requirement_id", "documents")):
        steps[(run_id, requirement_id)].append(documents)
    return {r.pk: note_for(r.run, steps.get((r.run_id, r.requirement_id), [])) for r in results}
