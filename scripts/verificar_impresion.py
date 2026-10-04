"""Comprueba con un navegador real la impresión de la matriz (REQ-032, ADR-0020 punto 5, T-086).

El navegador no está en la imagen de las pruebas, así que esto no corre en la suite: se repite
a mano cada vez que cambie `evaluon/static/tenders/print.css` o `matrix_print.html`.

Imprime cada vista con el navegador (Chromium/Edge de Playwright, `page.pdf()` con los
estilos de impresión) y comprueba, hoja por hoja, con la posición de las palabras:

- borrador y descartada: la leyenda "BORRADOR INCOMPLETO" está en cada hoja;
- validada: la leyenda no está en ninguna hoja y la marca "Matriz validada" está en cada una;
- en cada hoja ninguna otra palabra se superpone con la marca (el primer título de la hoja
  queda debajo de ella, no tapado) y hay contenido debajo.

Uso (requiere `pip install playwright pdfplumber` y un navegador; sale con 1 si algo falla):

    python scripts/verificar_impresion.py borrador=URL_o_archivo.html validada=... descartada=...

Cada destino es `tipo=dirección`: una URL de la vista de impresión
(`http://127.0.0.1:8000/procedimientos/matrices/N/imprimir/`; pide `EVALUON_USER` y
`EVALUON_PASSWORD` del entorno para ingresar) o un archivo HTML guardado con `print.css` al
lado. `EVALUON_BROWSER_CHANNEL` elige el navegador (por omisión `msedge`; vacío usa el
Chromium de Playwright). Con datos sintéticos solamente (P4).
"""

import io
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

import pdfplumber
from playwright.sync_api import sync_playwright

LEGEND = ("BORRADOR", "INCOMPLETO")
VALIDATED = ("Matriz", "validada")


def mark_box(words, needles):
    """El rectángulo de la marca: las palabras `needles` y las de su misma línea."""
    anchors = [w for w in words if w["text"] in needles]
    if not anchors:
        return None, []
    top = min(w["top"] for w in anchors)
    line = [w for w in words if abs(w["top"] - top) < 12 and w["top"] < top + 40]
    # La marca puede ocupar más de una línea: toda palabra pegada a las anclas.
    box = (min(w["x0"] for w in line), min(w["top"] for w in line),
           max(w["x1"] for w in line), max(w["bottom"] for w in line))
    return box, line


def overlaps(a, b):
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


def check(kind, data):
    problems = []
    with pdfplumber.open(io.BytesIO(data)) as document:
        sheets = len(document.pages)
        for number, page in enumerate(document.pages, start=1):
            words = page.extract_words()
            text = " ".join(w["text"] for w in words)
            needles = VALIDATED if kind == "validada" else LEGEND
            if kind == "validada" and "BORRADOR INCOMPLETO" in text:
                problems.append(f"hoja {number}: la validada lleva la leyenda")
            box, line = mark_box(words, needles[:1] if kind == "validada" else needles)
            if box is None:
                problems.append(f"hoja {number}: falta la marca")
                continue
            others = [w for w in words if w not in line]
            hidden = [w["text"] for w in others
                      if overlaps((w["x0"], w["top"], w["x1"], w["bottom"]), box)]
            if hidden:
                problems.append(f"hoja {number}: la marca tapa {hidden[:5]}")
            below = [w for w in others if w["top"] >= box[3] - 1]
            if not below:
                problems.append(f"hoja {number}: no hay contenido debajo de la marca")
            elif min(w["top"] for w in others) < box[1]:
                problems.append(f"hoja {number}: hay contenido por encima de la marca")
    return sheets, problems


def main(targets):
    failures = 0
    channel = os.environ.get("EVALUON_BROWSER_CHANNEL", "msedge") or None
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel=channel, headless=True)
        page = browser.new_page()
        for target in targets:
            kind, _, address = target.partition("=")
            if kind not in ("borrador", "descartada", "validada") or not address:
                sys.exit(f"destino no válido: {target}")
            if address.startswith("http"):
                base = "{0.scheme}://{0.netloc}".format(urlparse(address))
                page.goto(base + "/ingresar/")
                page.fill("input[name=username]", os.environ["EVALUON_USER"])
                page.fill("input[name=password]", os.environ["EVALUON_PASSWORD"])
                page.click("button[type=submit]")
                page.wait_for_load_state()
                page.goto(address)
            else:
                page.goto(Path(address).resolve().as_uri())
            page.emulate_media(media="print")
            data = page.pdf(prefer_css_page_size=True, print_background=True)
            sheets, problems = check(kind, data)
            if sheets < 2:
                problems.append("la matriz de prueba tiene una sola hoja: no prueba nada")
            print(f"{kind}: {sheets} hojas, {'SIN problemas' if not problems else 'FALLA'}")
            for problem in problems:
                print("  -", problem)
            failures += bool(problems)
        browser.close()
    return 1 if failures else 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1:]))
