"""Informe de lectura mínimo (REQ-004; ADR-0004, "Qué contiene el informe de lectura";
T-013).

En datos (`norms_reading.report`) y en texto legible (`norms_reading.report_text`):
páginas no leídas, unidades por tipo y por contenedor, tramos no ubicados, tramos
descartados (carátula, índice, títulos que pasan a la ruta), líneas descartadas
(encabezados y pies de página), control de secuencia (saltos, encabezados no aceptados y
encabezados dudosos de reconocimiento), párrafos en mayúsculas que quedaron dentro de una
unidad y párrafos que siguen al último inciso de una lista (T-023), uniones de palabras cortadas, control de cobertura y la lista de
unidades con su clave. El informe completo, con las diez partes del ADR-0004, es de
T-025.
"""

FIRST_WORDS = 8

# Nombre de cada tipo de unidad en el texto del informe: singular y plural.
TYPE_NAMES = {
    "anexo": ("anexo", "anexos"),
    "articulo": ("artículo", "artículos"),
    "inciso": ("inciso", "incisos"),
    "considerando": ("considerando", "considerandos"),
    "clausula": ("cláusula", "cláusulas"),
    "punto": ("punto", "puntos"),
    "parrafo": ("párrafo", "párrafos"),
}

DISCARD_REASONS = {
    "indice": "Índice",
    "titulo": "Título o capítulo, que pasa a la ruta",
    "caratula": "Carátula (membrete y datos GDE)",
}

BODY_CONTAINER = "Cuerpo"

# Nombre de cada regla de partición en el texto del informe (T-024).
RULE_NAMES = {"normas": "normas", "dictamenes": "dictámenes y recomendaciones"}


def first_words(text, count=FIRST_WORDS):
    """Las primeras palabras de un tramo, en una sola línea."""
    return " ".join(text.split()[:count])


def build_report(
    *,
    reading,
    canonical,
    units,
    segments,
    part,
    rules_version,
    containers,
    rule="normas",
    sequence=(),
    uppercase_in_units=(),
    doubtful_headings=(),
    after_last_inciso=(),
):
    """Arma el informe en datos. `segments` son los tramos no unitarios: pares
    (`"discarded"` o `"unlocated"`, inicio, fin, motivo)."""
    text = canonical.text
    discarded, unlocated = [], []
    for kind, start, end, reason in segments:
        page_start, page_end = canonical.pages_at(start, end)
        if kind == "discarded":
            discarded.append(
                {
                    "reason": reason,
                    "char_start": start,
                    "char_end": end,
                    "page_start": page_start,
                    "page_end": page_end,
                    "first_words": first_words(text[start:end]),
                }
            )
        else:
            unlocated.append(
                {
                    "char_start": start,
                    "char_end": end,
                    "page": page_start,
                    "first_words": first_words(text[start:end]),
                }
            )

    by_type = {}
    for unit in units:
        by_type[unit.unit_type] = by_type.get(unit.unit_type, 0) + 1
    by_container = []
    for container in containers:
        parent = container["key"] or None
        articles = [u for u in units if u.unit_type == "articulo" and u.parent_key == parent]
        by_container.append(
            {
                "container": container["name"],
                "key": container["key"],
                "articulo": len(articles),
                "first": articles[0].number if articles else None,
                "last": articles[-1].number if articles else None,
            }
        )

    return {
        "rules_version": rules_version,
        # Regla elegida por la categoría: `normas` o `dictamenes` (T-024).
        "rule": rule,
        "part": part,
        "pages": {"total": len(reading.pages), "not_read": list(reading.pages_not_read)},
        "units": {
            "total": len(units),
            "by_type": by_type,
            "by_container": by_container,
        },
        # Control de secuencia por contenedor: números que faltan (saltos aceptados
        # dentro del margen) y encabezados que no se aceptaron (repeticiones,
        # transcripciones, saltos grandes), con la unidad en la que quedaron. En un
        # dictamen, `heading` es "punto"; si falta, son artículos.
        "sequence": [dict(item) for item in sequence],
        # Párrafos en mayúsculas sin forma reconocida que quedaron dentro de una unidad
        # (decisión del responsable del 2026-10-03): para que los revise quien valida.
        "uppercase_in_units": list(uppercase_in_units),
        # Encabezados de artículo leídos por reconocimiento con el número mal leído o
        # fuera de secuencia, aceptados por la secuencia: requieren atención.
        "doubtful_headings": list(doubtful_headings),
        # Párrafos sin encabezado que siguen al último inciso de una lista: el PDF no
        # distingue sangrías, así que pueden ser del inciso o de la unidad que lo
        # contiene, donde quedaron. Clave del inciso, unidad donde quedaron y cuántos.
        "after_last_inciso": list(after_last_inciso),
        "unit_list": [
            {
                "key": unit.key,
                "unit_type": unit.unit_type,
                "label": unit.label,
                "path": unit.path,
                "page_start": unit.page_start,
                "page_end": unit.page_end,
            }
            for unit in units
        ],
        "unlocated": unlocated,
        "discarded": discarded,
        "discarded_lines": canonical.discarded_lines,
        "discarded_line_list": [
            {"page": line.page, "reason": line.reason, "text": line.text}
            for line in canonical.discarded
        ],
        "hyphen_joins": [{"page": join.page, "word": join.word} for join in canonical.hyphen_joins],
        "coverage": coverage(text, units, segments),
    }


def coverage(text, units, segments):
    """Control de cobertura: cada carácter del texto canónico está en una unidad base, en
    un tramo descartado, en un tramo no ubicado o es el salto de línea que separa dos
    tramos. La suma tiene que dar el total, sin solapamientos ni huecos."""
    # Los incisos son recortes de su artículo: cada carácter se cuenta en su unidad base.
    ranges = [("units", u.char_start, u.char_end) for u in units if u.unit_type != "inciso"]
    ranges += [(kind, start, end) for kind, start, end, _ in segments]
    ranges = sorted((r for r in ranges if r[2] > r[1]), key=lambda r: r[1])

    totals = {"units": 0, "discarded": 0, "unlocated": 0, "separators": 0}
    matches = True
    position = 0
    for index, (kind, start, end) in enumerate(ranges):
        gap = text[position:start]
        if start < position:
            matches = False  # dos tramos se solapan
        elif index and gap == "\n":
            totals["separators"] += 1
        elif gap:
            matches = False  # texto que no quedó en ningún tramo
        totals[kind] += end - start
        position = max(position, end)
    if position != len(text):
        matches = False

    return {"total": len(text), **totals, "matches": matches and sum(totals.values()) == len(text)}


def _plural(count, singular, plural):
    return f"{count} {singular if count == 1 else plural}"


def _pages(start, end):
    if start is None:
        return "sin página"
    if start == end:
        return f"página {start}"
    return f"páginas {start} a {end}"


def report_text(report):
    """El informe en texto legible, en español llano."""
    lines = ["Informe de lectura"]
    rule = RULE_NAMES.get(report["rule"], report["rule"])
    lines.append(
        f"Reglas de partición: versión {report['rules_version']}, de {rule}. Parte: {report['part']}."
    )

    pages = report["pages"]
    not_read = ", ".join(str(number) for number in pages["not_read"]) or "ninguna"
    lines.append(f"Páginas: {pages['total']}. Páginas no leídas: {not_read}.")

    units = report["units"]
    kinds = ", ".join(
        _plural(count, *TYPE_NAMES.get(unit_type, (unit_type, unit_type)))
        for unit_type, count in units["by_type"].items()
    )
    lines.append(f"Unidades reconocidas: {units['total']}" + (f" ({kinds})." if kinds else "."))
    for container in units["by_container"]:
        count = container["articulo"]
        if count:
            span = f"del {container['first']} al {container['last']}"
            lines.append(f"  {container['container']}: {_plural(count, 'artículo', 'artículos')}, {span}.")
        else:
            lines.append(f"  {container['container']}: ningún artículo.")
    for item in report["sequence"]:
        if item["gaps"]:
            lines.append(f"  {item['container']}: faltan los números {', '.join(item['gaps'])}.")
        for heading in item["not_accepted"]:
            inside = f", quedó dentro de {heading['inside']}" if heading["inside"] else ""
            where = _pages(heading["page"], heading["page"])
            lines.append(
                f"  {item['container']}: encabezado del {item.get('heading', 'artículo')} "
                f"{heading['number']} fuera de secuencia, {where}{inside}."
            )

    doubtful = report["doubtful_headings"]
    if doubtful:
        lines.append(
            "Requiere atención: "
            + _plural(len(doubtful), "encabezado dudoso leído", "encabezados dudosos leídos")
            + " por reconocimiento sobre imagen y aceptado por la secuencia."
        )
        for item in doubtful:
            lines.append(f"  - {item['key']}, {_pages(item['page'], item['page'])}: {item['label']}")

    upper = report["uppercase_in_units"]
    if upper:
        lines.append(f"Párrafos en mayúsculas dentro de una unidad, para revisar: {len(upper)}.")
        for item in upper:
            lines.append(
                f"  - {item['key']}, {_pages(item['page'], item['page'])}: {item['first_words']}"
            )

    after = report["after_last_inciso"]
    if after:
        lines.append(
            "Párrafos después del último inciso de una lista, que pueden ser del inciso y "
            f"quedaron en la unidad que lo contiene, para revisar: {len(after)}."
        )
        for item in after:
            stayed = "párrafo quedó" if item["paragraphs"] == 1 else "párrafos quedaron"
            lines.append(
                f"  - {item['key']}, {_pages(item['page'], item['page'])}: "
                f"{item['paragraphs']} {stayed} en {item['inside']}"
            )

    unlocated = report["unlocated"]
    lines.append(f"No ubicado: {_plural(len(unlocated), 'tramo', 'tramos')}.")
    for item in unlocated:
        where = _pages(item["page"], item["page"]).capitalize()
        lines.append(f"  - {where}: {item['first_words']}")

    discarded = report["discarded"]
    lines.append(f"Descartado: {_plural(len(discarded), 'tramo', 'tramos')}.")
    for item in discarded:
        reason = DISCARD_REASONS.get(item["reason"], item["reason"])
        lines.append(
            f"  - {reason}, {_pages(item['page_start'], item['page_end'])}: {item['first_words']}"
        )
    if report["discarded_lines"]:
        lines.append(f"Líneas descartadas en la lectura: {report['discarded_lines']}.")

    joins = report["hyphen_joins"]
    lines.append(f"Uniones de palabras cortadas: {len(joins)}.")
    for join in joins:
        lines.append(f"  - {_pages(join['page'], join['page'])}: {join['word']}")

    cover = report["coverage"]
    verdict = "la suma coincide con el total" if cover["matches"] else "la suma NO coincide con el total"
    lines.append(
        f"Cobertura: {cover['total']} caracteres: {cover['units']} en unidades, "
        f"{cover['discarded']} descartados, {cover['unlocated']} no ubicados y "
        f"{cover['separators']} saltos de línea entre tramos; {verdict}."
    )

    lines.append("Unidades:")
    for item in report["unit_list"]:
        lines.append(
            f"  {item['key']} · {item['path']} · {item['label']} · "
            f"{_pages(item['page_start'], item['page_end'])}"
        )
    return "\n".join(lines) + "\n"
