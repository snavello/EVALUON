"""El contrato de los mosaicos del tablero (plan 017, «Tablero: mosaicos y detalle»; ADR-0076;
definición compartida 2; T-313).

Cada tema de una sección declara `tiles(user, procedure, ctx) -> list[Tile]`, con `ctx` el
contexto que ya calculó su `context()`. El detalle que abre un mosaico es el parcial de un tema
(`d-` más su clave) o un `Detail` propio que el tema declara con `details(user, procedure, ctx)`.
Si un parámetro de la consulta abre un modo del tema (`?oferta=`, `?ficha=`, `?historial=`), el
tema declara también `opens(request) -> str | None` con el id del detalle.

Regla de REQ-141: si `big` es `None` el mosaico dice `missing` («Falta …» o «Pendiente») y no se
dibuja ni la cifra ni el gráfico. No hay valor por omisión para la cifra.
"""

from dataclasses import dataclass, field

WIDTHS = (1, 2, 4)
TONES = ("", "dark")


def detail_id(tema_key):
    """El id del detalle de un tema: `s3_ofertas` -> `d-s3-ofertas`."""
    return "d-" + tema_key.replace("_", "-")


@dataclass(frozen=True)
class Tile:
    """Un mosaico del tablero.

    - `key`: nombre corto, único en la sección (da el id del mosaico).
    - `detail`: id del detalle que abre (`d-s3-ofertas`). Vacío solo si hay `href`.
    - `width`: columnas que ocupa (1, 2 o 4). `tone`: `""` o `dark`.
    - `big` y `unit`: la cifra grande y su unidad; `None` si el sistema no tiene el dato.
    - `sub`: línea de apoyo. `chart`: uno de los gráficos de `charts.py`.
    - `missing`: lo que se dice cuando `big` es `None` («Falta …» o «Pendiente»).
    - `href`: si el mosaico lleva a otra pantalla (los del primer panel) en lugar de abrir un
      detalle de esta.
    """

    key: str
    title: str
    detail: str = ""
    width: int = 1
    tone: str = ""
    big: object = None
    unit: str = ""
    sub: str = ""
    chart: object = None
    missing: str = "Pendiente"
    href: str = ""

    def __post_init__(self):
        if self.width not in WIDTHS:
            raise ValueError(f"Ancho de mosaico inválido: {self.width!r} (válidos: {WIDTHS}).")
        if self.tone not in TONES:
            raise ValueError(f"Tono de mosaico inválido: {self.tone!r} (válidos: {TONES}).")
        if not self.detail and not self.href:
            raise ValueError(f"El mosaico {self.key!r} no abre ningún detalle ni enlaza a nada.")

    @property
    def has_data(self):
        """Hay dato si `big` no es `None` ni vacío. El cero es un dato (REQ-141)."""
        return self.big is not None and self.big != ""

    @property
    def classes(self):
        return f"tile w{self.width}" + (f" {self.tone}" if self.tone else "")


@dataclass(frozen=True)
class Detail:
    """Un detalle que un tema declara además del de su parcial (por ejemplo, el orden
    económico). Se dibuja con `template` y `context`."""

    id: str
    title: str
    template: str
    context: dict = field(default_factory=dict)


@dataclass
class Board:
    """Lo que la vista pasa a la plantilla: mosaicos, detalles, los temas sin mosaico (que
    siguen mostrándose como hoy) y el detalle que abre la consulta."""

    tiles: list
    details: list  # [Detail] en el orden en que aparecen
    leftover: list  # temas cuyo parcial no es el detalle de ningún mosaico
    abre: str | None = None


def build_board(section, user, procedure, contexts, request=None):
    """El tablero de `section`, o `None` si ningún tema declara mosaicos (la sección se muestra
    como antes). `contexts` es {clave del tema: su `context()`}."""
    tiles = section.tiles(user, procedure, contexts)
    if not tiles:
        return None
    titles = {}
    for tile in tiles:
        if tile.detail:
            titles.setdefault(tile.detail, tile.title)
    wanted = {tile.detail for tile in tiles if tile.detail}
    details, owned = [], set()
    for tema in section.temas:
        default = detail_id(tema.KEY)
        if default in wanted:
            details.append(Detail(default, titles[default], tema.PARTIAL,
                                  {"t": contexts.get(tema.KEY)}))
            owned.add(tema.KEY)
    details += section.details(user, procedure, contexts)
    leftover = [tema for tema in section.temas if tema.KEY not in owned]
    return Board(tiles=tiles, details=details, leftover=leftover,
                 abre=section.opens(request) if request is not None else None)
