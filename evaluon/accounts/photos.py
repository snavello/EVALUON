"""Fotos del primer panel (REQ-136, REQ-138; plan 017, "Fotos"; ADR-0073).

`pick_for(request)` devuelve qué foto dibujar. Por ahora devuelve siempre la foto de la casa;
la elección al azar entre las fotos del usuario la completa T-319 sin cambiar la forma del
resultado (`Picked`: `photo_id`, `label`, `url`).

`reference_histogram()` calcula una sola vez el histograma de la foto de la casa; es el tono al
que T-319 ajusta cada foto subida.
"""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from django.conf import settings
from django.templatetags.static import static
from django.urls import reverse

HOUSE_PHOTO = "diseno/casa/biblioratos-bn.jpg"
HOUSE_LABEL = "Foto de la casa"
OWN_LABEL = "Foto de su perfil"


@dataclass(frozen=True)
class Picked:
    """La foto elegida. `photo_id` es `None` para la foto de la casa."""

    photo_id: int | None
    label: str

    @property
    def url(self):
        """Se calcula al dibujar: la estática de la casa o la vista que sirve la foto propia."""
        if self.photo_id is None:
            return static(HOUSE_PHOTO)
        return reverse("accounts:foto", args=[self.photo_id])


def pick_for(request):
    """La foto para el pedido. T-308: siempre la de la casa."""
    return Picked(photo_id=None, label=HOUSE_LABEL)


def house_photo_path():
    return Path(settings.BASE_DIR) / "evaluon" / "static" / HOUSE_PHOTO


@lru_cache(maxsize=1)
def reference_histogram():
    """Histograma de 256 niveles de gris de la foto de la casa (una tupla, calculada una vez)."""
    from PIL import Image

    with Image.open(house_photo_path()) as image:
        return tuple(image.convert("L").histogram())
