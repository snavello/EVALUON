"""Agrega avisos a tasks.md y cambia el estado de una tarea.

Uso: py -3 avisos.py tasks.md avisos.json
avisos.json: {"estado": ["T-015", "terminada"], "avisos": {"T-014": "texto", ...}}
"""
import io
import json
import re
import sys

ORDER = ["pendiente", "bloqueada", "en curso", "en verificación", "terminada"]
path, cfg = sys.argv[1], json.load(io.open(sys.argv[2], encoding="utf-8"))
s = io.open(path, encoding="utf-8", newline="").read().replace("\r\n", "\n")
assert "<<<<<<<" not in s and ">>>>>>>" not in s, "tasks.md tiene marcas de conflicto"

if cfg.get("estado"):
    tid, new = cfg["estado"]
    pat = re.compile(r"^(\| %s \|.*\| )([^|]+)( \|)$" % re.escape(tid), re.M)
    assert len(pat.findall(s)) == 1, "fila no encontrada: " + tid
    s = pat.sub(lambda m: m.group(1) + new + m.group(3), s)

avisos = cfg.get("avisos", {})
lines = s.split("\n")
out, cur, done = [], None, set()
for i, line in enumerate(lines):
    if line.startswith("### T-"):
        cur = line[4:9]
    if cur in avisos and cur not in done and line.startswith("- **Aviso de tareas anteriores:**"):
        out.append(line + " " + avisos[cur])
        done.add(cur)
        continue
    out.append(line)
    if (cur in avisos and cur not in done and line.startswith(("- **Qué hay que hacer:**", "- **Qué hacer:**"))
            and not lines[i + 1].startswith("- **Aviso")):
        out.append("- **Aviso de tareas anteriores:** " + avisos[cur])
        done.add(cur)
assert done == set(avisos), "sin aplicar: %s" % (set(avisos) - done)
s = "\n".join(out)
assert all("\n" not in v for v in avisos.values())
io.open(path, "w", encoding="utf-8", newline="").write(s)
print("ok", cfg.get("estado"), sorted(done))
