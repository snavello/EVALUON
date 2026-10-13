"""Genera los recursos de la marca que sirve la aplicación (REQ-108, T-267).

Se corre a mano, una sola vez (o cuando cambie la marca aprobada). No lo importa la aplicación
ni ningún test, y no entra en `pyproject.toml` ni en la imagen.

Qué hace
--------
Las fuentes aprobadas (`docs/diseno/marca/`) dibujan «EVALU» y «ON» como `<text>` con Arial: el
equipo que las abre necesita esa fuente. Para que la marca se vea igual en cualquier equipo,
este script reemplaza cada `<text>` por un `<g>` (mismo `fill` y `filter`) con un `<path>` por
letra, tomando de la Arial Bold los contornos, los anchos y los pares de crenado. Después recorta
los logotipos a la placa (`viewBox="126 144 772 224"`), les quita el halo exterior desenfocado
del bloque ON (el `rect` con `filter="url(#brillo)"` y la definición de ese filtro) y escribe:

    evaluon/static/marca/logotipo-encabezado.svg   (desde logotipo-fondo-oscuro.svg)
    evaluon/static/marca/logotipo-ingreso.svg      (desde logotipo-fondo-claro.svg)
    evaluon/static/marca/isotipo.svg               (copia de isotipo-fondo-claro.svg)

Cómo se corre
-------------
`fontTools` no es una dependencia del proyecto: se instala en un entorno temporal fuera del
repositorio.

    python -m venv %TEMP%/marca-venv
    %TEMP%/marca-venv/Scripts/python -m pip install fonttools==4.66.1
    %TEMP%/marca-venv/Scripts/python tools/marca_a_contornos.py [--fuente RUTA_ARIAL_BOLD]

Versión usada para generar los recursos: fontTools 4.66.1, con Arial Bold 'arialbd.ttf' de
Windows (por omisión `C:/Windows/Fonts/arialbd.ttf`; variable de entorno MARCA_FUENTE o
`--fuente` para otra ruta).

Crenado: se aplican los pares de la tabla `kern` de la fuente (el único par de EVALUON con
ajuste es V-A). Se comprobó contra el navegador (Edge) superponiendo el original con `<text>`
y el generado; ver el registro de verificación de T-267.
"""

import argparse
import os
import re
import shutil
import sys
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1]
FUENTE_POR_OMISION = "C:/Windows/Fonts/arialbd.ttf"
MARCA = ROOT / "docs" / "diseno" / "marca"
SALIDA = ROOT / "evaluon" / "static" / "marca"
VIEWBOX = "126 144 772 224"

LOGOTIPOS = {
    "logotipo-fondo-oscuro.svg": "logotipo-encabezado.svg",
    "logotipo-fondo-claro.svg": "logotipo-ingreso.svg",
}

TEXTO = re.compile(r"<text\b([^>]*)>([^<]*)</text>")
HALO = re.compile(r'[ \t]*<rect\b[^>]*filter="url\(#brillo\)"[^>]*/>[ \t]*\n')
FILTRO_HALO = re.compile(r'[ \t]*<filter id="brillo".*?</filter>[ \t]*\n', re.S)


def atributo(atributos, nombre):
    """Valor del atributo `nombre` dentro de `atributos`, o None."""
    m = re.search(rf'\b{re.escape(nombre)}="([^"]*)"', atributos)
    return m.group(1) if m else None


def numero(valor):
    """Número corto y estable para el SVG."""
    texto = f"{valor:.2f}".rstrip("0").rstrip(".")
    return "0" if texto in ("-0", "") else texto


class Fuente:
    def __init__(self, ruta):
        self.ttf = TTFont(ruta)
        self.cmap = self.ttf.getBestCmap()
        self.glifos = self.ttf.getGlyphSet()
        self.hmtx = self.ttf["hmtx"]
        self.unidades = self.ttf["head"].unitsPerEm
        self.pares = {}
        if "kern" in self.ttf:
            for tabla in self.ttf["kern"].kernTables:
                self.pares.update(tabla.kernTable)

    def contornos(self, texto, x, y, ancla, tamano):
        """Un `d` por letra de `texto`, ya colocado en (x, y) con el ancla pedida."""
        nombres = [self.cmap[ord(c)] for c in texto]
        escala = tamano / self.unidades
        posiciones, cursor = [], 0
        for i, nombre in enumerate(nombres):
            posiciones.append(cursor)
            cursor += self.hmtx[nombre][0]
            if i + 1 < len(nombres):
                cursor += self.pares.get((nombre, nombres[i + 1]), 0)
        ancho = cursor * escala
        if ancla == "middle":
            inicio = x - ancho / 2
        elif ancla == "end":
            inicio = x - ancho
        else:
            inicio = x
        resultado = []
        for nombre, posicion in zip(nombres, posiciones):
            lapiz = SVGPathPen(self.glifos, ntos=numero)
            # Eje Y invertido; el glifo se coloca sobre la línea base y.
            transformacion = (escala, 0, 0, -escala, inicio + posicion * escala, y)
            self.glifos[nombre].draw(TransformPen(lapiz, transformacion))
            resultado.append(lapiz.getCommands())
        return resultado


def a_contornos(svg, fuente):
    def reemplazo(m):
        atributos, texto = m.group(1), m.group(2)
        x = float(atributo(atributos, "x"))
        y = float(atributo(atributos, "y"))
        ancla = atributo(atributos, "text-anchor") or "start"
        tamano = float(atributo(atributos, "font-size"))
        relleno, filtro = atributo(atributos, "fill"), atributo(atributos, "filter")
        extra = f' filter="{filtro}"' if filtro else ""
        trazos = "".join(f'<path d="{d}"/>'
                         for d in fuente.contornos(texto, x, y, ancla, tamano))
        return f'<g fill="{relleno}"{extra}>{trazos}</g>'

    return TEXTO.sub(reemplazo, svg)


def generar(fuente):
    SALIDA.mkdir(parents=True, exist_ok=True)
    for origen, destino in LOGOTIPOS.items():
        svg = (MARCA / origen).read_text(encoding="utf-8")
        svg = a_contornos(svg, fuente)
        svg = HALO.sub("", svg)
        svg = FILTRO_HALO.sub("", svg)
        svg = re.sub(r'viewBox="[^"]*"', f'viewBox="{VIEWBOX}"', svg, count=1)
        for malo in ("<text", "brillo", "font-family"):
            assert malo not in svg, malo
        (SALIDA / destino).write_text(svg, encoding="utf-8", newline="\n")
        print("escrito", SALIDA / destino)
    shutil.copyfile(MARCA / "isotipo-fondo-claro.svg", SALIDA / "isotipo.svg")
    print("copiado", SALIDA / "isotipo.svg")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--fuente", default=os.environ.get("MARCA_FUENTE", FUENTE_POR_OMISION))
    argumentos = parser.parse_args()
    if not Path(argumentos.fuente).is_file():
        sys.exit(f"No se encontró la fuente {argumentos.fuente}")
    generar(Fuente(argumentos.fuente))


if __name__ == "__main__":
    main()
