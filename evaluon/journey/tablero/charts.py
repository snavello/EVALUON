"""Los siete gráficos SVG del tablero (plan 017, «Gráficos»; definición compartida 3; T-314).

Cada gráfico es una dataclass con el atributo de clase `template`; el mosaico lo dibuja con
`{% include chart.template %}` y la variable `chart`. Toda la geometría se calcula acá y llega a
la plantilla como texto con punto decimal (la localización argentina escribiría una coma y
rompería el dibujo).

Reglas de la guía visual (`docs/diseno/guia-visual.md`, 4 y 5):

- Todo SVG usa atributos de presentación y `currentColor`; el color sale de una clase `g-*` que
  en `tablero.css` solo declara `color: var(--…)`. Nunca `style=` (la política de contenido es
  `default-src 'self'`).
- Toda marca lima va sobre una marca `g-ink` un poco mayor, dibujada justo antes: así el contorno
  `--ink` se logra solo con clases de color (en el tema gris y blanco el lima casi no se
  distingue del fondo).
- Valores `None` o series vacías no dibujan ninguna marca ni cifra (REQ-141): `has_data` es
  falso y el SVG queda solo con su título.
- `--s2` y `--s3` quedan a 1,54:1 en el tema negro: las series vecinas de un apilado se
  separan con un hueco y con la leyenda, nunca solo con esos dos colores.
"""

import itertools
import math
from dataclasses import dataclass, field
from decimal import Decimal
from functools import cached_property
from typing import ClassVar

# Tonos de una marca: la clase es `g-<tono>`. `lime` pide su contorno `ink` (ver arriba).
TONES = ("ok", "no", "nd", "pe", "ext", "lime", "ink", "mute", "s3")
# Todas las clases `g-*` que usan las plantillas de gráficos. `tablero.css` declara de cada una
# `color: var(--…)`: ok, no, nd, pe, ext, lime, ink y s3 con el token del mismo nombre, `mute`
# con `--s2`, `ink2` con `--ink-2` y `line` con `--line`.
CLASSES = frozenset({f"g-{tone}" for tone in TONES} | {"g-ink2", "g-line"})

_SEQUENCE = itertools.count(1)

STACK_ORDER = ("ink", "mute", "s3", "ext", "ok", "nd")
TIMELINE_STATES = ("past", "now", "future", "pending")
DONUT_STATES = (("ok", "Cumple"), ("no", "No cumple"), ("nd", "No determinado"),
                ("pe", "Pendiente"))


# --- Ayudas ------------------------------------------------------------------------------------


def _n(value):
    """Un número para un atributo SVG: punto decimal, hasta tres decimales y sin ceros de más."""
    text = f"{float(value):.3f}".rstrip("0").rstrip(".")
    return "0" if text in ("", "-0") else text


def _f(value):
    """El valor como `float`, o `None` si no hay."""
    if value is None or isinstance(value, bool):
        return None
    return float(value)


def _plain(value):
    """Un número para leer: entero sin decimales, o con coma decimal."""
    number = float(value)
    if number == int(number):
        return str(int(number))
    return f"{number:.2f}".rstrip("0").rstrip(".").replace(".", ",")


def _thousands(number):
    return f"{int(round(number)):,}".replace(",", ".")


def _tone(tone):
    if tone not in TONES:
        raise ValueError(f"Tono de gráfico desconocido: {tone!r} (válidos: {', '.join(TONES)}).")
    return tone


def _nice_step(raw):
    exponent = math.floor(math.log10(raw))
    fraction = raw / 10 ** exponent
    nice = 1 if fraction <= 1.5 else 2 if fraction <= 3 else 5 if fraction <= 7 else 10
    return nice * 10 ** exponent


# --- Base --------------------------------------------------------------------------------------


@dataclass(kw_only=True)
class Chart:
    """Lo común de los siete gráficos: título y descripción accesibles y el prefijo de los ids
    (`uid`, único en la página; por omisión se genera uno con el tipo y un número)."""

    title: str = ""
    desc: str = ""
    uid: str = ""

    template: ClassVar[str] = ""
    kind: ClassVar[str] = ""

    def __post_init__(self):
        # Sin `uid`, cada gráfico genera el suyo: dos del mismo tipo en una página no repiten ids.
        if not self.uid:
            self.uid = f"{self.kind}-{next(_SEQUENCE)}"

    @property
    def ident(self):
        return self.uid

    @property
    def title_id(self):
        return f"{self.ident}-t"

    @property
    def desc_id(self):
        return f"{self.ident}-d"

    @property
    def has_data(self):
        raise NotImplementedError

    @property
    def description(self):
        """La descripción escrita, o una armada con los datos."""
        if self.desc:
            return self.desc
        return self._auto_desc() if self.has_data else "Sin datos para dibujar."

    def _auto_desc(self):
        raise NotImplementedError


# --- Barras horizontales ---------------------------------------------------------------------------


@dataclass
class BarRow:
    label: str
    value: object
    text: str = ""
    tone: str = "ink"
    maximum: object = None

    def __post_init__(self):
        _tone(self.tone)


@dataclass(kw_only=True)
class Bars(Chart):
    """Barras horizontales (avance por sección, documentos por oferta)."""

    rows: list = field(default_factory=list)
    maximum: object = None

    template: ClassVar[str] = "journey/graficos/_bars.html"
    kind: ClassVar[str] = "bars"

    WIDTH: ClassVar[int] = 360
    PITCH: ClassVar[int] = 24
    TRACK_X: ClassVar[int] = 116
    TRACK_W: ClassVar[int] = 180

    @cached_property
    def _valid(self):
        return [r for r in self.rows if _f(r.value) is not None]

    @property
    def has_data(self):
        return bool(self._valid)

    @property
    def view_box(self):
        return f"0 0 {self.WIDTH} {max(len(self._valid), 1) * self.PITCH}"

    @cached_property
    def geometry(self):
        peak = _f(self.maximum) or max((_f(r.value) for r in self._valid), default=0)
        found = []
        for i, row in enumerate(self._valid):
            top = i * self.PITCH
            limit = _f(row.maximum) or peak
            ratio = min(max(_f(row.value) / limit, 0), 1) if limit and limit > 0 else 0
            width = ratio * self.TRACK_W
            found.append({
                "label": row.label, "text": row.text or _plain(row.value),
                "ty": _n(top + 15), "y": _n(top + 8), "tx": self.WIDTH,
                "x": self.TRACK_X, "track": self.TRACK_W, "w": _n(width), "draw": width > 0,
                "tone": row.tone, "lime": row.tone == "lime",
                "ox": _n(self.TRACK_X - 1.5), "oy": _n(top + 8 - 1.5),
                "ow": _n(width + 3), "oh": 11,
            })
        return found

    def _auto_desc(self):
        return "; ".join(f"{g['label']} {g['text']}" for g in self.geometry) + "."


# --- Donas por oferta ----------------------------------------------------------------------------


@dataclass
class DonutItem:
    """Cumple, no cumple, no determinado y pendiente de una oferta (cantidades de requisitos)."""

    label: str
    ok: int = 0
    no: int = 0
    nd: int = 0
    pe: int = 0

    @property
    def counts(self):
        return {state: max(int(getattr(self, state) or 0), 0) for state, _ in DONUT_STATES}

    @property
    def total(self):
        return sum(self.counts.values())


@dataclass(kw_only=True)
class Donuts(Chart):
    """Una dona por oferta con sus cuatro estados."""

    items: list = field(default_factory=list)

    template: ClassVar[str] = "journey/graficos/_donuts.html"
    kind: ClassVar[str] = "donuts"

    CELL: ClassVar[int] = 100
    RADIUS: ClassVar[int] = 28

    @cached_property
    def _valid(self):
        return [i for i in self.items if i.total > 0]

    @property
    def has_data(self):
        return bool(self._valid)

    @cached_property
    def _width(self):
        return max(len(self._valid) * self.CELL, 4 * self.CELL)

    @property
    def view_box(self):
        return f"0 0 {self._width} 124"

    @cached_property
    def geometry(self):
        circumference = 2 * math.pi * self.RADIUS
        left = (self._width - len(self._valid) * self.CELL) / 2
        found = []
        for i, item in enumerate(self._valid):
            cx = left + i * self.CELL + self.CELL / 2
            counts = {s: c for s, c in item.counts.items() if c > 0}
            gap = 2 if len(counts) > 1 else 0
            done, arcs = 0.0, []
            for state, count in counts.items():
                length = count / item.total * circumference
                dash = max(length - gap, 0.5)
                arcs.append({"tone": state, "dash": _n(dash), "rest": _n(circumference - dash),
                             "offset": _n(-done)})
                done += length
            found.append({
                "label": item.label, "cx": _n(cx), "cy": 42, "r": self.RADIUS,
                "rotate": f"rotate(-90 {_n(cx)} 42)", "arcs": arcs,
                "center": f"{item.counts['ok']}/{item.total}", "ty": 47, "ly": 92,
            })
        return found

    @cached_property
    def legend(self):
        left = (self._width - 4 * self.CELL) / 2
        return [{"tone": state, "name": name, "x": _n(left + k * self.CELL + 6),
                 "tx": _n(left + k * self.CELL + 16)} for k, (state, name) in
                enumerate(DONUT_STATES)]

    def _auto_desc(self):
        parts = []
        for item in self._valid:
            counts = item.counts
            parts.append(f"{item.label}: {counts['ok']} cumplen, {counts['no']} no cumplen, "
                         f"{counts['nd']} no determinados, {counts['pe']} pendientes")
        return "; ".join(parts) + "."


# --- Lollipop (orden económico) --------------------------------------------------------------------


@dataclass
class LollipopRow:
    """Una oferta del orden económico. Las filas llegan ya de menor a mayor; `low` y `high`
    marcan la más baja y la más alta; `text` es el monto y `note` la aclaración de abajo."""

    label: str
    value: object
    text: str = ""
    note: str = ""
    low: bool = False
    high: bool = False


@dataclass(kw_only=True)
class Lollipop(Chart):
    """Orden económico de menor a mayor, con la más baja y la más alta como indicadores."""

    rows: list = field(default_factory=list)

    template: ClassVar[str] = "journey/graficos/_lollipop.html"
    kind: ClassVar[str] = "lollipop"

    WIDTH: ClassVar[int] = 560  # ancho mínimo; crece si un texto no entra (H-1)
    LEFT: ClassVar[int] = 84
    PLOT: ClassVar[int] = 326
    MARGIN: ClassVar[int] = 6
    PITCH: ClassVar[int] = 40
    TOP: ClassVar[int] = 14

    @cached_property
    def _valid(self):
        return [r for r in self.rows if _f(r.value) is not None]

    @property
    def has_data(self):
        return bool(self._valid)

    @cached_property
    def _width(self):
        """El ancho del dibujo: el mínimo, o el que hace falta para que el monto y la nota de
        cada punto entren (0,6 del cuerpo por letra, una cota alta del ancho real)."""
        ends = [self._x(_f(r.value)) + 14 + max(len(r.text) * 0.6 * 12, len(r.note) * 0.6 * 10)
                for r in self._valid]
        return max(self.WIDTH, math.ceil(max(ends, default=0) + self.MARGIN))

    @property
    def view_box(self):
        return f"0 0 {self._width} {self.TOP + len(self._valid) * self.PITCH + 22}"

    @cached_property
    def _domain(self):
        values = [_f(r.value) for r in self._valid]
        low, high = min(values), max(values)
        span = high - low
        pad = span * 0.15 if span else (abs(low) * 0.1 or 1)
        start = low - pad
        if low >= 0:
            start = max(start, 0)
        return start, high + pad

    def _x(self, value):
        start, end = self._domain
        return self.LEFT + (value - start) / (end - start) * self.PLOT

    @cached_property
    def geometry(self):
        found = []
        for i, row in enumerate(self._valid):
            y = self.TOP + i * self.PITCH + 8
            x = self._x(_f(row.value))
            found.append({
                "label": row.label, "text": row.text, "note": row.note,
                "x": _n(x), "y": _n(y), "x1": self.LEFT, "ty": _n(y + 4),
                "vx": _n(x + 14), "vy": _n(y - 1), "ny": _n(y + 13),
                "low": row.low, "high": row.high and not row.low,
                "outer": _n(8.5), "inner": _n(6.5),
            })
        return found

    @cached_property
    def ticks(self):
        start, end = self._domain
        step = _nice_step((end - start) / 4)
        tick = math.ceil(start / step) * step
        base = self.TOP + len(self._valid) * self.PITCH
        found = []
        while tick <= end + step * 1e-9:
            found.append({"x": _n(self._x(tick)), "label": self._tick_label(tick, step),
                          "y1": self.TOP - 4, "y2": _n(base - 6), "ty": _n(base + 10)})
            tick += step
        return found

    @staticmethod
    def _tick_label(value, step):
        if abs(value) >= 1e6 and step >= 1e5:
            return f"{value / 1e6:.1f}".rstrip("0").rstrip(".").replace(".", ",") + " M"
        if step >= 1:
            return _thousands(value)
        return f"{value:.2f}".replace(".", ",")

    def _auto_desc(self):
        return "; ".join(
            " ".join(part for part in (r.label, r.text or _plain(r.value), r.note) if part)
            for r in self._valid) + "."


# --- Línea de tiempo (plazos) ----------------------------------------------------------------------


@dataclass
class TimelineEvent:
    """Un hito. `state`: `past` (ya pasó), `now` (hoy), `future` o `pending` (todavía no hay
    fecha). La forma de la marca distingue cada estado, no solo el color."""

    label: str
    date: str = ""
    state: str = "future"

    def __post_init__(self):
        if self.state not in TIMELINE_STATES:
            raise ValueError(f"Estado de hito desconocido: {self.state!r}.")


@dataclass(kw_only=True)
class Timeline(Chart):
    """Plazos importantes, uno debajo del otro, con lo que ya pasó, lo de hoy y lo que viene."""

    events: list = field(default_factory=list)

    template: ClassVar[str] = "journey/graficos/_timeline.html"
    kind: ClassVar[str] = "timeline"

    WIDTH: ClassVar[int] = 360
    PITCH: ClassVar[int] = 34

    @property
    def has_data(self):
        return bool(self.events)

    @property
    def view_box(self):
        return f"0 0 {self.WIDTH} {max(len(self.events), 1) * self.PITCH}"

    @cached_property
    def geometry(self):
        return [{"label": e.label, "date": e.date, "state": e.state,
                 "y": _n(i * self.PITCH + self.PITCH / 2), "ty": _n(i * self.PITCH + 21)}
                for i, e in enumerate(self.events)]

    @cached_property
    def axis(self):
        """La línea vertical entre el primer hito y el último (con uno solo no hay línea)."""
        if len(self.events) < 2:
            return None
        return {"y1": _n(self.PITCH / 2), "y2": _n((len(self.events) - 1) * self.PITCH
                                                   + self.PITCH / 2)}

    def _auto_desc(self):
        return "; ".join(f"{e.date} {e.label}".strip() for e in self.events) + "."


# --- Barra apilada ------------------------------------------------------------------------------


@dataclass
class StackPart:
    label: str
    value: object
    tone: str | None = None
    text: str = ""

    def __post_init__(self):
        if self.tone is not None:
            _tone(self.tone)


@dataclass(kw_only=True)
class Stack(Chart):
    """Una barra apilada (la matriz por tipo de requisito), con su leyenda."""

    parts: list = field(default_factory=list)

    template: ClassVar[str] = "journey/graficos/_stack.html"
    kind: ClassVar[str] = "stack"

    WIDTH: ClassVar[int] = 360
    GAP: ClassVar[int] = 2
    BAR: ClassVar[int] = 16
    LEGEND_PITCH: ClassVar[int] = 18

    @cached_property
    def _known(self):
        return [p for p in self.parts if _f(p.value) is not None]

    @cached_property
    def _positive(self):
        return [p for p in self._known if _f(p.value) > 0]

    @property
    def has_data(self):
        return bool(self._positive)

    @property
    def view_box(self):
        return f"0 0 {self.WIDTH} {self.BAR + 12 + len(self._known) * self.LEGEND_PITCH}"

    def _tone_of(self, part, index):
        return part.tone or STACK_ORDER[index % len(STACK_ORDER)]

    @cached_property
    def geometry(self):
        total = sum(_f(p.value) for p in self._positive)
        room = self.WIDTH - self.GAP * (len(self._positive) - 1)
        left, found = 0.0, []
        for i, part in enumerate(self._positive):
            width = _f(part.value) / total * room
            tone = self._tone_of(part, i)
            found.append({"label": part.label, "x": _n(left), "w": _n(width), "h": self.BAR,
                          "tone": tone, "lime": tone == "lime", "ox": _n(left - 1.5),
                          "ow": _n(width + 3), "oy": -1.5, "oh": self.BAR + 3})
            left += width + self.GAP
        return found

    @cached_property
    def legend(self):
        tones = {id(p): self._tone_of(p, i) for i, p in enumerate(self._positive)}
        found = []
        for i, part in enumerate(self._known):
            tone = tones.get(id(part)) or self._tone_of(part, len(self._positive))
            top = self.BAR + 12 + i * self.LEGEND_PITCH
            found.append({"text": f"{part.label} {part.text or _plain(part.value)}",
                          "tone": tone, "lime": tone == "lime", "y": _n(top),
                          "ty": _n(top + 9)})
        return found

    def _auto_desc(self):
        return "; ".join(f"{p.label} {p.text or _plain(p.value)}" for p in self._known) + "."


# --- Columnas chicas --------------------------------------------------------------------------


@dataclass
class ColumnItem:
    """Una columna: `text` es la cifra corta que se ve arriba; `note`, el texto completo del
    título flotante."""

    label: str
    value: object
    text: str = ""
    highlight: bool = False
    note: str = ""


@dataclass(kw_only=True)
class Columns(Chart):
    """Columnas chicas (los totales de las ofertas), con la destacada en lima."""

    items: list = field(default_factory=list)

    template: ClassVar[str] = "journey/graficos/_columns.html"
    kind: ClassVar[str] = "columns"

    PITCH: ClassVar[int] = 54
    COLUMN: ClassVar[int] = 34
    PLOT: ClassVar[int] = 70
    TOP: ClassVar[int] = 16

    @cached_property
    def _valid(self):
        return [i for i in self.items if _f(i.value) is not None and _f(i.value) >= 0]

    @property
    def has_data(self):
        return bool(self._valid)

    @property
    def view_box(self):
        return f"0 0 {max(len(self._valid), 1) * self.PITCH + 6} {self.TOP + self.PLOT + 24}"

    @cached_property
    def geometry(self):
        peak = max((_f(i.value) for i in self._valid), default=0)
        base = self.TOP + self.PLOT
        found = []
        for k, item in enumerate(self._valid):
            height = _f(item.value) / peak * self.PLOT if peak > 0 else 0
            x = 3 + k * self.PITCH + (self.PITCH - self.COLUMN) / 2
            found.append({
                "label": item.label, "text": item.text,
                "title": f"{item.label}: {item.note or item.text or _plain(item.value)}",
                "x": _n(x), "y": _n(base - height), "w": self.COLUMN, "h": _n(height),
                "draw": height > 0, "highlight": item.highlight,
                "ox": _n(x - 1.5), "oy": _n(base - height - 1.5), "ow": self.COLUMN + 3,
                "oh": _n(height + 1.5), "cx": _n(x + self.COLUMN / 2),
                "ty": _n(base - height - 4), "ly": _n(base + 15),
            })
        return found

    @property
    def baseline(self):
        return {"x2": _n(max(len(self._valid), 1) * self.PITCH + 6), "y": self.TOP + self.PLOT}

    def _auto_desc(self):
        return "; ".join(f"{i.label} {i.note or i.text or _plain(i.value)}"
                         for i in self._valid) + "."


# --- Tabla de calor -------------------------------------------------------------------------------


@dataclass
class HeatCell:
    """Cuántos requisitos cumple (`value`) de cuántos hay (`total`) en una celda."""

    value: object
    total: object


@dataclass
class HeatRow:
    label: str
    cells: list = field(default_factory=list)


@dataclass(kw_only=True)
class Heat(Chart):
    """Tabla de calor: cumplimiento por tipo (filas) y oferta (columnas). Una celda sin dato o
    con total cero queda vacía."""

    columns: list = field(default_factory=list)
    rows: list = field(default_factory=list)

    template: ClassVar[str] = "journey/graficos/_heat.html"
    kind: ClassVar[str] = "heat"

    LABEL: ClassVar[int] = 96
    CELL_W: ClassVar[int] = 64
    CELL_H: ClassVar[int] = 26
    GAP: ClassVar[int] = 4
    HEAD: ClassVar[int] = 22
    MAX_TINT: ClassVar[float] = 0.55

    def _cell(self, cell):
        if cell is None or _f(cell.value) is None or not _f(cell.total):
            return None
        return cell

    @cached_property
    def _filled(self):
        return [(i, j, c) for i, row in enumerate(self.rows)
                for j, raw in enumerate(row.cells[:len(self.columns)])
                if (c := self._cell(raw)) is not None]

    @property
    def has_data(self):
        return bool(self._filled)

    @property
    def view_box(self):
        width = self.LABEL + len(self.columns) * (self.CELL_W + self.GAP)
        height = self.HEAD + len(self.rows) * (self.CELL_H + self.GAP)
        return f"0 0 {width} {height}"

    @cached_property
    def geometry(self):
        if not self.has_data:
            return {"cols": [], "rows": [], "cells": []}
        step_x, step_y = self.CELL_W + self.GAP, self.CELL_H + self.GAP
        cells = []
        for i, j, cell in self._filled:
            ratio = min(max(_f(cell.value) / _f(cell.total), 0), 1)
            tint = ratio * self.MAX_TINT
            cells.append({
                "x": _n(self.LABEL + j * step_x), "y": _n(self.HEAD + i * step_y),
                "w": self.CELL_W, "h": self.CELL_H, "opacity": _n(tint), "tint": tint > 0,
                "text": f"{_plain(cell.value)}/{_plain(cell.total)}",
                "tx": _n(self.LABEL + j * step_x + self.CELL_W / 2),
                "ty": _n(self.HEAD + i * step_y + self.CELL_H / 2 + 4),
            })
        return {
            "cols": [{"label": c, "x": _n(self.LABEL + j * step_x + self.CELL_W / 2)}
                     for j, c in enumerate(self.columns)],
            "rows": [{"label": r.label, "y": _n(self.HEAD + i * step_y + self.CELL_H / 2 + 4)}
                     for i, r in enumerate(self.rows)],
            "cells": cells,
        }

    def _auto_desc(self):
        parts = []
        for i, j, cell in self._filled:
            parts.append(f"{self.rows[i].label}, {self.columns[j]}: {_plain(cell.value)} de "
                         f"{_plain(cell.total)}")
        return "; ".join(parts) + "."
