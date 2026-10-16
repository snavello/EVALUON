#!/usr/bin/env python3
"""Genera el glosario de códigos del proyecto: qué es cada T-NNN, REQ-NNN, ADR-NNNN,
D-/H-/O-NNN-N, EV-NNN, P-N y feature NNN, leído de specs/, docs/adr/ y evals/.

Uso:
    python tools/glosario.py                  escribe docs/glosario.md
    python tools/glosario.py --html RUTA      escribe además el fragmento HTML de la solapa
    python tools/glosario.py --root CARPETA   lee otra copia de trabajo

No se edita a mano: se regenera como el tablero (docs/tablero.md).
"""
from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path

PREFIJOS = [
    ("T-NNN", "Tarea de una feature (código y tests); vive en specs/NNN/tasks.md"),
    ("REQ-NNN", "Requisito funcional de una spec; único en el proyecto"),
    ("ADR-NNNN", "Decisión de arquitectura registrada en docs/adr/"),
    ("D-NNN-N", "Hallazgo de una verificación que impide o condiciona (defecto); NNN es la tarea verificada"),
    ("H-NNN-N", "Hallazgo de una verificación (misma idea que D-, nombre usado desde la 016)"),
    ("O-NNN-N", "Observación de una verificación: no impide integrar"),
    ("M-NNN", "Entrada de la lista esperada de un caso (un requisito que la matriz debe traer); fuera de git"),
    ("EV-NNN", "Caso del conjunto dorado de evals (pregunta pública con respuesta esperada)"),
    ("P1 a P11", "Principio de la constitución"),
    ("NNN", "Feature de la hoja de ruta (001, 003, …, 016)"),
    ("caso-0N", "Caso público del corpus (pliego, circulares y, en el 00, ofertas y dictamen)"),
]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def plain(text: str, limit: int = 120) -> str:
    """Quita marcas de Markdown y recorta en una palabra."""
    t = re.sub(r"`([^`]*)`", r"\1", text)
    t = re.sub(r"\*\*([^*]*)\*\*", r"\1", t)
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t)
    t = re.sub(r"\s+", " ", t).strip()
    if len(t) <= limit:
        return t
    cut = t[:limit].rsplit(" ", 1)[0]
    return cut.rstrip(" ,;:(") + "…"


def feature_rows(root: Path) -> list[dict]:
    rows = []
    for line in read(root / "specs" / "hoja-de-ruta.md").splitlines():
        if re.match(r"^\| \d{3} \|", line):
            c = cells(line)
            rows.append({"codigo": c[0], "tipo": "Feature", "feature": c[0],
                         "que": f"{c[1]}: {plain(c[2], 110)}", "estado": ""})
    return rows


def feature_folders(root: Path) -> list[Path]:
    return sorted(p for p in (root / "specs").iterdir()
                  if p.is_dir() and re.match(r"^\d{3}-", p.name))


def task_rows(root: Path) -> list[dict]:
    rows = []
    for folder in feature_folders(root):
        path = folder / "tasks.md"
        if not path.exists():
            continue
        for line in read(path).splitlines():
            if re.match(r"^\| T-\d{3}[a-z]? \|", line):
                c = cells(line)
                rows.append({"codigo": c[0], "tipo": "Tarea", "feature": folder.name[:3],
                             "que": plain(c[1], 120), "estado": c[-1]})
    return rows


def req_rows(root: Path) -> list[dict]:
    rows = []
    for folder in feature_folders(root):
        path = folder / "spec.md"
        if not path.exists():
            continue
        text = read(path)
        header = next((l for l in text.splitlines() if l.startswith("| ID |")), "")
        idx = 2 if "Hoja" in header else 1
        for line in text.splitlines():
            if re.match(r"^\| REQ-\d{3} \|", line):
                c = cells(line)
                rows.append({"codigo": c[0], "tipo": "Requisito", "feature": folder.name[:3],
                             "que": plain(c[idx], 120), "estado": ""})
    return rows


def adr_rows(root: Path) -> list[dict]:
    rows = []
    for path in sorted((root / "docs" / "adr").glob("[0-9]*.md")):
        lines = read(path).splitlines()
        if not lines or path.name.startswith("0000"):
            continue
        m = re.match(r"^# (ADR-\d{4}) · (.*)$", lines[0])
        if not m:
            continue
        estado = ""
        for l in lines[1:6]:
            e = re.search(r"Estado: ([^·]+)", l)
            if e:
                estado = e.group(1).strip()
                break
        rows.append({"codigo": m.group(1), "tipo": "ADR", "feature": "",
                     "que": plain(m.group(2), 110), "estado": estado})
    return rows


HALLAZGO = re.compile(r"\*\*([DHO]-\d{3}-\d+)\b([^*]*)\*\*\s*(.{0,220})")


def finding_rows(root: Path) -> list[dict]:
    rows: dict[str, dict] = {}
    for folder in feature_folders(root):
        ver = folder / "verificacion"
        for path in sorted(ver.glob("*.md")) if ver.exists() else []:
            for m in HALLAZGO.finditer(read(path)):
                code = m.group(1)
                if code in rows:
                    continue
                resto = (m.group(2) + " " + m.group(3)).strip(" .:·")
                tipo = {"D": "Hallazgo", "H": "Hallazgo", "O": "Observación"}[code[0]]
                rows[code] = {"codigo": code, "tipo": tipo, "feature": folder.name[:3],
                              "que": plain(resto.split(". ")[0], 130), "estado": path.stem}
        tasks = folder / "tasks.md"
        if tasks.exists():
            for line in read(tasks).splitlines():
                if re.match(r"^\| [DHO]-\d{3}-\d+", line):
                    c = cells(line)
                    code = c[0]
                    if code in rows:
                        continue
                    tipo = {"D": "Hallazgo", "H": "Hallazgo", "O": "Observación"}[code[0]]
                    rows[code] = {"codigo": code, "tipo": tipo, "feature": folder.name[:3],
                                  "que": plain(c[2], 130), "estado": plain(c[1], 40)}
    return sorted(rows.values(), key=lambda r: r["codigo"])


def eval_rows(root: Path) -> list[dict]:
    rows = []
    for path in sorted((root / "evals" / "casos").glob("EV-*.yaml")):
        q = ""
        for line in read(path).splitlines():
            if line.startswith("pregunta:"):
                q = line.split(":", 1)[1].strip().strip('"')
                break
        rows.append({"codigo": path.stem, "tipo": "Eval", "feature": "001",
                     "que": plain(q, 110), "estado": ""})
    return rows


def principle_rows(root: Path) -> list[dict]:
    rows = []
    for line in read(root / "specs" / "constitution.md").splitlines():
        m = re.match(r"^### (P\d+)\. (.*)$", line)
        if m:
            rows.append({"codigo": m.group(1), "tipo": "Principio", "feature": "",
                         "que": plain(m.group(2), 110), "estado": ""})
    return rows


def collect(root: Path) -> list[dict]:
    return (principle_rows(root) + feature_rows(root) + task_rows(root) + req_rows(root)
            + adr_rows(root) + finding_rows(root) + eval_rows(root))


def md_table(rows: list[dict], estado: str) -> list[str]:
    out = [f"| Código | Feature | Qué es | {estado} |", "|---|---|---|---|"]
    for r in rows:
        out.append(f"| **{r['codigo']}** | {r['feature']} | {r['que']} | {r['estado']} |")
    return out


def build_md(rows: list[dict]) -> str:
    out = ["# Glosario de códigos", "",
           "> Se genera con `python tools/glosario.py` a partir de `specs/`, `docs/adr/` y `evals/`. No editar a mano.",
           "", "Qué significa cada prefijo:", "", "| Prefijo | Qué es |", "|---|---|"]
    out += [f"| **{p}** | {q} |" for p, q in PREFIJOS]
    for tipo, estado in [("Principio", ""), ("Feature", ""), ("Tarea", "Estado"), ("Requisito", ""),
                         ("ADR", "Estado"), ("Hallazgo", "Dónde"), ("Observación", "Dónde"), ("Eval", "")]:
        sub = [r for r in rows if r["tipo"] == tipo]
        if not sub:
            continue
        titulo = {"Principio": "Principios de la constitución", "Feature": "Features",
                  "Tarea": "Tareas", "Requisito": "Requisitos", "ADR": "Decisiones (ADR)",
                  "Hallazgo": "Hallazgos de verificación", "Observación": "Observaciones de verificación",
                  "Eval": "Casos de evals"}[tipo]
        out += ["", f"## {titulo} ({len(sub)})", ""] + md_table(sub, estado or "·")
    return "\n".join(out) + "\n"


def build_html(rows: list[dict]) -> str:
    """Fragmento para una solapa: buscador más una tabla con todos los códigos."""
    e = html.escape
    filas = "\n".join(
        f'<tr><td><b>{e(r["codigo"])}</b></td><td>{e(r["tipo"])}</td><td>{e(r["feature"])}</td>'
        f'<td>{e(r["que"])}</td><td>{e(r["estado"])}</td></tr>' for r in rows)
    prefijos = "\n".join(f"<tr><td><b>{e(p)}</b></td><td>{e(q)}</td></tr>" for p, q in PREFIJOS)
    return f"""<h2>Códigos del proyecto</h2>
<p>Qué es cada código que aparece en tareas, informes y mensajes. Escribí un código o una palabra para filtrar; {len(rows)} entradas, generadas desde los specs.</p>
<p><input id="glos-filtro" type="search" placeholder="Por ejemplo T-300, D-60, REQ-120, circulares" aria-label="Filtrar códigos" style="width:100%;padding:9px 12px;font-size:15px;border:1px solid #D9D2C1;border-radius:6px"></p>
<details><summary>Qué significa cada prefijo</summary><div class="tabla-desliza"><table><thead><tr><th>Prefijo</th><th>Qué es</th></tr></thead><tbody>
{prefijos}
</tbody></table></div></details>
<div class="tabla-desliza"><table id="glos-tabla"><thead><tr><th>Código</th><th>Tipo</th><th>Feature</th><th>Qué es</th><th>Estado o dónde</th></tr></thead><tbody>
{filas}
</tbody></table></div>
<p id="glos-cuenta" class="meta"></p>
<script>
(function () {{
  var filtro = document.getElementById("glos-filtro");
  var filas = Array.prototype.slice.call(document.querySelectorAll("#glos-tabla tbody tr"));
  var cuenta = document.getElementById("glos-cuenta");
  function norm(s) {{ return s.toLowerCase().normalize("NFD").replace(/[\\u0300-\\u036f]/g, ""); }}
  function aplicar() {{
    var q = norm(filtro.value.trim());
    var n = 0;
    filas.forEach(function (tr) {{
      var ok = !q || norm(tr.textContent).indexOf(q) !== -1;
      tr.hidden = !ok; if (ok) n++;
    }});
    cuenta.textContent = q ? n + " de " + filas.length + " entradas" : filas.length + " entradas";
  }}
  filtro.addEventListener("input", aplicar);
  aplicar();
}})();
</script>
"""


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    ap.add_argument("--html", default=None, help="escribe además el fragmento HTML de la solapa")
    args = ap.parse_args(argv)
    root = Path(args.root)
    rows = collect(root)
    out = root / "docs" / "glosario.md"
    out.write_text(build_md(rows), encoding="utf-8")
    print(f"Escrito {out.relative_to(root)} ({len(rows)} códigos)")
    if args.html:
        Path(args.html).write_text(build_html(rows), encoding="utf-8")
        print(f"Escrito {args.html}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
