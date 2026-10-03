"""Resuelve conflictos de merge en tasks.md.

- Filas de la tabla: se queda con el estado más avanzado de cada tarea.
- Una línea de aviso en cada lado: une los dos agregados.
- Cualquier otro conflicto: termina con error sin escribir nada.
"""
import io
import os
import re
import sys

ORDER = {"pendiente": 0, "bloqueada": 1, "en curso": 2, "en verificación": 3, "terminada": 4}
p = sys.argv[1]
s = io.open(p, encoding="utf-8", newline="").read().replace("\r\n", "\n")


def rows(lines):
    d = {}
    for line in lines:
        m = re.match(r"\| (T-\d+) \|", line)
        if not m:
            return None
        d[m.group(1)] = line
    return d


def status(line):
    return ORDER[line.rstrip(" |").split("|")[-1].strip()]


out, i, n = [], 0, 0
while True:
    a = s.find("<<<<<<< ", i)
    if a < 0:
        out.append(s[i:])
        break
    a_end = s.index("\n", a) + 1
    m = s.index("\n=======\n", a)
    e = s.index("\n>>>>>>> ", m)
    e2 = s.index("\n", e + 1) + 1
    ours = s[a_end:m].split("\n")
    theirs = s[m + 9:e].split("\n")
    o, t = rows(ours), rows(theirs)
    if o is not None and t is not None:
        ids = sorted(set(o) | set(t), key=lambda x: int(x[2:]))
        res = [max([x for x in (o.get(k), t.get(k)) if x], key=status) for k in ids]
    elif len(ours) == 1 and len(theirs) == 1 and ours[0].startswith("- **Aviso") and theirs[0].startswith("- **Aviso"):
        pre = os.path.commonprefix([ours[0], theirs[0]])
        res = [ours[0] + " " + theirs[0][len(pre):].lstrip()]
    else:
        sys.exit("conflicto no reconocido: " + ours[0][:80])
    out.append(s[i:a] + "\n".join(res) + "\n")
    i = e2
    n += 1
s = "".join(out)
assert "<<<<<<<" not in s and ">>>>>>>" not in s
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("resueltos", n)
