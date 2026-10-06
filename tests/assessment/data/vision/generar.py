"""Genera las dos imágenes inventadas de la lectura con visión (T-160; P4): una página de texto
dibujada como imagen y una foto de una tabla de precios, con una leve inclinación y ruido.
Nada es real: la empresa, los números y los precios son inventados. Se corre una vez y los PNG
quedan en esta carpeta: `python generar.py [carpeta de salida]`."""

import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent

PAGE_LINES = [
    "CONSTANCIA DE PRUEBA N° 0000/00",
    "",
    "La empresa Papelera Ficticia S.A., con domicilio en la calle Imaginaria 123,",
    "declara que mantiene su oferta por el plazo de sesenta días corridos y que",
    "entregará los bienes en el depósito inventado número 7 dentro de los cinco días",
    "hábiles de recibida la orden de compra.",
    "",
    "Garantía de mantenimiento de oferta: póliza número 998877 por $ 125.000,00.",
    "Fecha de la constancia: 15 de marzo de 2024.",
]

TABLE = [
    ("Renglón", "Descripción", "Cantidad", "Precio unitario"),
    ("1", "Resma de papel A4 75 g", "100", "$ 3.150,00"),
    ("2", "Carpeta oficio con solapas", "40", "$ 820,50"),
    ("3", "Bolígrafo azul caja x 50", "12", "$ 4.075,00"),
]


FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"  # trae las tildes


def font(size):
    return ImageFont.truetype(FONT, size)


def text_page(path):
    image = Image.new("RGB", (1240, 1754), "white")
    draw = ImageDraw.Draw(image)
    y = 140
    for line in PAGE_LINES:
        draw.text((110, y), line, fill="black", font=font(28))
        y += 56
    image.save(path)


def table_photo(path):
    rng = random.Random(7)
    image = Image.new("RGB", (1500, 900), (236, 232, 222))
    draw = ImageDraw.Draw(image)
    draw.text((90, 60), "CUADRO DE PRECIOS INVENTADO", fill=(20, 20, 20), font=font(36))
    columns = [90, 260, 760, 1000, 1400]
    top, height = 140, 110
    for row, values in enumerate(TABLE):
        y = top + row * height
        for index, value in enumerate(values):
            draw.text((columns[index] + 14, y + 36), value, fill=(25, 25, 25), font=font(32))
        draw.line([(columns[0], y), (columns[-1], y)], fill=(40, 40, 40), width=3)
    bottom = top + len(TABLE) * height
    draw.line([(columns[0], bottom), (columns[-1], bottom)], fill=(40, 40, 40), width=3)
    for x in columns:
        draw.line([(x, top), (x, bottom)], fill=(40, 40, 40), width=3)
    image = image.rotate(1.8, resample=Image.BICUBIC, fillcolor=(236, 232, 222))
    pixels = image.load()
    for _ in range(9000):
        x, y = rng.randrange(image.width), rng.randrange(image.height)
        shade = rng.randrange(-25, 10)
        r, g, b = pixels[x, y]
        pixels[x, y] = (max(0, r + shade), max(0, g + shade), max(0, b + shade))
    image.filter(ImageFilter.GaussianBlur(0.6)).save(path)


if __name__ == "__main__":
    text_page(OUT / "pagina-texto.png")
    table_photo(OUT / "foto-tabla.png")
