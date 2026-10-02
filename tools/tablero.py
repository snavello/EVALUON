#!/usr/bin/env python3
"""Genera docs/tablero.md: qué se hizo y qué falta, leído de specs/.

Uso:
    python tools/tablero.py           escribe docs/tablero.md
    python tools/tablero.py --check   falla si docs/tablero.md está desactualizado

No tiene dependencias externas. Los diagramas son Mermaid, que GitHub dibuja
al abrir el archivo.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

STAGES = ["Spec", "Plan", "Tareas", "Desarrollo", "Verificación", "Auditoría", "Despliegue"]

# Estado de tarea -> (símbolo, clase Mermaid). El símbolo va siempre en la
# etiqueta para que el estado se lea aunque no se distingan los colores.
TASK_STATES = {
    "terminada": ("✓", "done"),
    "en verificación": ("◐", "review"),
    "en curso": ("▶", "active"),
    "bloqueada": ("✕", "blocked"),
    "pendiente": ("○", "todo"),
}

MERMAID_CLASSES = """\
  classDef done fill:#1a7f37,stroke:#116329,color:#ffffff
  classDef review fill:#0969da,stroke:#0550ae,color:#ffffff
  classDef active fill:#bf8700,stroke:#7d4e00,color:#ffffff
  classDef blocked fill:#cf222e,stroke:#a40e26,color:#ffffff
  classDef todo fill:#eaeef2,stroke:#8c959f,color:#24292f"""

LEGEND = "✓ hecho · ▶ en curso · ◐ en verificación · ○ pendiente · ✕ bloqueada"

COMMIT_RE = re.compile(r"^(T-\d+)\s*\(")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def field(text: str, name: str) -> str:
    """Valor de 'Nombre: valor' hasta el separador (· o |) o el fin de línea."""
    match = re.search(rf"\b{name}:\**\s*([^·|\n]+)", text)
    return match.group(1).strip().lower() if match else ""


def table_rows(text: str, first_cell: str) -> list[list[str]]:
    """Filas de tabla Markdown cuya primera celda coincide con el patrón."""
    rows = []
    for line in text.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if cells and re.fullmatch(first_cell, cells[0]):
            rows.append(cells)
    return rows


def label(text: str, limit: int = 44) -> str:
    """Texto seguro para una etiqueta Mermaid entre comillas."""
    text = re.sub(r"[`\[\]{}<>]", "", text.replace('"', "'")).strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def cell(text: str) -> str:
    return text.replace("|", "\\|")


def bar(done: int, total: int, width: int = 10) -> str:
    if not total:
        return "—"
    filled = round(width * done / total)
    return f"{'█' * filled}{'░' * (width - filled)} {round(100 * done / total)}%"


def task_commits(root: Path) -> dict[str, list[tuple[str, str, str]]]:
    """Commits con formato 'T-NNN (REQ-NNN): ...', agrupados por tarea."""
    try:
        out = subprocess.run(
            ["git", "log", "--date=short", "--pretty=%h\t%ad\t%s"],
            cwd=root, capture_output=True, text=True, check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return {}
    commits: dict[str, list[tuple[str, str, str]]] = {}
    for line in out.splitlines():
        sha, date, subject = (line.split("\t", 2) + ["", ""])[:3]
        match = COMMIT_RE.match(subject)
        if match:
            commits.setdefault(match.group(1), []).append((sha, date, subject))
    return commits


def load_feature(folder: Path, root: Path) -> dict:
    number, _, slug = folder.name.partition("-")
    spec = read(folder / "spec.md")
    plan = read(folder / "plan.md")
    tasks_md = read(folder / "tasks.md")

    heading = re.search(r"^#\s*(.+)$", spec, re.M)
    title = heading.group(1) if heading else slug.replace("-", " ")
    title = re.sub(r"^Spec\s+\d+\s*[·:-]\s*", "", title).strip()

    tasks = []
    for row in table_rows(tasks_md, r"T-\d+"):
        row += [""] * (5 - len(row))
        state = row[4].lower()
        tasks.append({
            "id": row[0],
            "title": row[1],
            "reqs": re.findall(r"REQ-\d+", row[2]),
            "deps": re.findall(r"T-\d+", row[3]),
            "state": state if state in TASK_STATES else "pendiente",
        })

    audits = sorted((root / "docs" / "auditorias").glob(f"{number}-*.md"))
    feature = {
        "number": number,
        "title": title,
        "path": folder.relative_to(root).as_posix(),
        "spec_state": field(spec, "Estado") if spec else "",
        "plan_state": field(plan, "Estado") if plan else "",
        "open_questions": spec.count("[A ACLARAR"),
        "reqs": [(r[0], r[1] if len(r) > 1 else "") for r in table_rows(spec, r"REQ-\d+")],
        "tasks": tasks,
        "report": (folder / "informe-pruebas.md").is_file(),
        "audit": field(read(audits[-1]), "Resultado") if audits else "",
        "deploy": field(tasks_md, "Despliegue"),
    }
    feature["stages_done"] = stages_done(feature)
    return feature


def stages_done(f: dict) -> int:
    """Cantidad de etapas completas, en orden; se corta en la primera que falta."""
    states = [t["state"] for t in f["tasks"]]
    checks = [
        f["spec_state"].startswith("aprobad"),
        f["plan_state"].startswith("aprobad"),
        bool(states),
        all(s in ("en verificación", "terminada") for s in states),
        all(s == "terminada" for s in states) and f["report"],
        f["audit"].startswith("aprobado"),
        f["deploy"].startswith("aprobado"),
    ]
    done = 0
    for ok in checks:
        if not ok:
            break
        done += 1
    return done


def next_step(f: dict) -> str:
    done = f["stages_done"]
    if done == len(STAGES):
        return "Feature terminada."
    open_tasks = sum(t["state"] != "terminada" for t in f["tasks"])
    if done == 0:
        if not f["spec_state"]:
            return "Escribir la spec."
        doubts = f["open_questions"]
        prefix = f"Resolver {doubts} duda{'s' if doubts != 1 else ''} marcada{'s' if doubts != 1 else ''} en la spec y " if doubts else ""
        text = prefix + "aprobar la spec (compuerta del responsable)."
        return text[0].upper() + text[1:]
    return [
        "",
        "El planificador entrega `plan.md`; lo aprueba el responsable." if not f["plan_state"]
        else "Aprobar el plan (compuerta del responsable).",
        "El planificador desglosa el plan en `tasks.md`.",
        f"Desarrollar: {open_tasks} tarea{'s' if open_tasks != 1 else ''} sin terminar.",
        "Verificar: el testeador evaluador cierra las tareas y entrega `informe-pruebas.md`.",
        "Auditoría: dictamen del auditor en `docs/auditorias/`.",
        "Despliegue: lo prepara el implementador y lo aprueba el responsable.",
    ][done]


def stage_summary(f: dict) -> str:
    done = f["stages_done"]
    if done == len(STAGES):
        return "Terminada"
    return f"{done + 1} de {len(STAGES)} · {STAGES[done]}"


def stages_diagram(f: dict) -> str:
    done = f["stages_done"]
    nodes = []
    for i, name in enumerate(STAGES):
        symbol, css = ("✓", "done") if i < done else ("▶", "active") if i == done else ("○", "todo")
        nodes.append(f'E{i}["{symbol} {i + 1}. {name}"]:::{css}')
    return "```mermaid\nflowchart LR\n  " + " --> ".join(nodes) + "\n" + MERMAID_CLASSES + "\n```"


def tasks_diagram(f: dict) -> str:
    lines = ["```mermaid", "flowchart TD"]
    ids = {t["id"] for t in f["tasks"]}
    for t in f["tasks"]:
        symbol, css = TASK_STATES[t["state"]]
        node = t["id"].replace("-", "")
        lines.append(f'  {node}["{symbol} {t["id"]} · {label(t["title"])}"]:::{css}')
    for t in f["tasks"]:
        for dep in t["deps"]:
            if dep in ids:
                lines.append(f'  {dep.replace("-", "")} --> {t["id"].replace("-", "")}')
    return "\n".join(lines) + "\n" + MERMAID_CLASSES + "\n```"


def roadmap_rows(root: Path) -> list[dict]:
    rows = []
    for row in table_rows(read(root / "specs" / "hoja-de-ruta.md"), r"\d{3}"):
        row += [""] * (4 - len(row))
        rows.append({"number": row[0], "title": row[1], "delivers": row[2],
                     "deps": re.findall(r"\d{3}", row[3])})
    return rows


def project_section(features: list[dict], roadmap: list[dict]) -> list[str]:
    by_number = {f["number"]: f for f in features}
    items = list(roadmap)
    known = {r["number"] for r in items}
    for f in features:  # features con carpeta que la hoja de ruta no menciona
        if f["number"] not in known:
            items.append({"number": f["number"], "title": f["title"], "delivers": "", "deps": []})
    items.sort(key=lambda r: r["number"])

    out = ["## Proyecto", ""]
    if not items:
        return out + ["Todavía no hay features. La primera se crea en `specs/001-nombre/`.", ""]

    diagram = ["```mermaid", "flowchart LR"]
    table = ["| Feature | Qué entrega | Etapa | Tareas | Avance |", "|---|---|---|---|---|"]
    numbers = {r["number"] for r in items}
    for r in items:
        f = by_number.get(r["number"])
        if not f:
            symbol, css, stage, tasks_txt, progress = "○", "todo", "No iniciada", "—", "—"
        else:
            total = len(f["tasks"])
            finished = sum(t["state"] == "terminada" for t in f["tasks"])
            complete = f["stages_done"] == len(STAGES)
            symbol, css = ("✓", "done") if complete else ("▶", "active")
            stage = stage_summary(f)
            tasks_txt = f"{finished}/{total}" if total else "—"
            progress = bar(finished, total)
        diagram.append(f'  F{r["number"]}["{symbol} {r["number"]} · {label(r["title"], 30)}"]:::{css}')
        name = f'[{r["number"]} · {cell(r["title"])}](#{r["number"]})' if f else f'{r["number"]} · {cell(r["title"])}'
        table.append(f'| {name} | {cell(r["delivers"]) or "—"} | {stage} | {tasks_txt} | {progress} |')
    for r in items:
        for dep in r["deps"]:
            if dep in numbers:
                diagram.append(f'  F{dep} --> F{r["number"]}')
    diagram += [MERMAID_CLASSES, "```"]
    return out + diagram + [""] + table + [""]


def feature_section(f: dict, commits: dict) -> list[str]:
    out = [f'<a id="{f["number"]}"></a>', "", f'## {f["number"]} · {f["title"]}', ""]
    detail = []
    if f["stages_done"] == 0 and f["spec_state"]:
        detail.append(f'spec en {f["spec_state"]}')
    if f["open_questions"]:
        detail.append(f'{f["open_questions"]} dudas abiertas')
    suffix = f" ({', '.join(detail)})" if detail else ""
    out += [f'**Etapa actual:** {stage_summary(f)}{suffix} · [carpeta]({"../" + f["path"]})', "",
            stages_diagram(f), ""]

    out += ["### Qué falta", "", f"- **Próximo paso:** {next_step(f)}"]
    for state in ("bloqueada", "en curso", "en verificación", "pendiente"):
        for t in f["tasks"]:
            if t["state"] == state:
                out.append(f'- {TASK_STATES[state][0]} {t["id"]} · {t["title"]} ({state})')
    out.append("")

    out += ["### Qué se hizo", ""]
    finished = [t for t in f["tasks"] if t["state"] == "terminada"]
    milestones = [name for name in STAGES[: f["stages_done"]]]
    if milestones:
        out.append("- Etapas completas: " + ", ".join(milestones) + ".")
    for t in finished:
        refs = ", ".join(f"`{sha}` {date}" for sha, date, _ in commits.get(t["id"], []))
        out.append(f'- ✓ {t["id"]} · {t["title"]}' + (f" ({refs})" if refs else ""))
    if not milestones and not finished:
        out.append("- Nada terminado todavía.")
    out.append("")

    if f["tasks"]:
        out += ["### Mapa de tareas", "", tasks_diagram(f), ""]

    if f["reqs"]:
        out += ["### Requisitos", "", "| Requisito | Descripción | Tareas | Estado |", "|---|---|---|---|"]
        for req_id, text in f["reqs"]:
            covering = [t for t in f["tasks"] if req_id in t["reqs"]]
            if not covering:
                status = "sin tarea" if f["tasks"] else "—"
            elif any(t["state"] == "bloqueada" for t in covering):
                status = "✕ bloqueado"
            elif all(t["state"] == "terminada" for t in covering):
                status = "✓ cubierto"
            else:
                status = "▶ en proceso" if any(t["state"] != "pendiente" for t in covering) else "○ pendiente"
            ids = ", ".join(t["id"] for t in covering) or "—"
            out.append(f"| {req_id} | {cell(text)} | {ids} | {status} |")
        out.append("")
    return out


def build(root: Path) -> str:
    specs = root / "specs"
    folders = sorted(p for p in specs.iterdir() if p.is_dir() and re.match(r"\d{3}-", p.name)) if specs.is_dir() else []
    features = [load_feature(folder, root) for folder in folders]
    commits = task_commits(root)

    out = ["# Tablero de avance", "",
           "> Se genera con `python tools/tablero.py` a partir de `specs/`. No editar a mano.", "",
           f"Leyenda: {LEGEND}", ""]
    out += project_section(features, roadmap_rows(root))
    for f in features:
        out += feature_section(f, commits)
    return "\n".join(out).rstrip() + "\n"


def main(argv: list[str]) -> int:
    root = Path(__file__).resolve().parent.parent
    target = root / "docs" / "tablero.md"
    content = build(root)
    if "--check" in argv:
        if read(target) != content:
            print("docs/tablero.md está desactualizado: correr python tools/tablero.py")
            return 1
        print("docs/tablero.md está al día")
        return 0
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    print(f"Escrito {target.relative_to(root)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
