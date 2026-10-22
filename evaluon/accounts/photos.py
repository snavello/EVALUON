"""Fotos del primer panel (REQ-136, REQ-137, REQ-138; plan 017, "Fotos"; ADR-0073).

- `upload(user, file)`: valida el contenido, ajusta la foto al tono de la casa y la guarda en la
  base (la primera ranura libre; la restricción única de la base cubre la subida simultánea).
- `remove(user, photo_id)`: borrado real, solo del dueño.
- `pick_for(request)`: qué foto dibujar, al azar entre las del usuario sin repetir la anterior.
- `reference_histogram()`: histograma de la foto de la casa, calculado una sola vez; es el tono
  al que se ajusta cada foto subida.

Solo se guarda la foto ajustada (JPEG en blanco y negro, sin metadatos): no se conserva el
original. Nada de esto usa IA ni sale del equipo (P4).
"""

import hashlib
import io
import random
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from django.conf import settings
from django.db import IntegrityError, transaction
from django.templatetags.static import static
from django.urls import NoReverseMatch, reverse
from PIL import Image, ImageOps, UnidentifiedImageError

from evaluon.accounts.models import PHOTO_MAX_BYTES, PHOTO_SLOTS, Photo

HOUSE_PHOTO = "diseno/casa/biblioratos-bn.jpg"
HOUSE_LABEL = "Foto de la casa"
OWN_LABEL = "Foto de su perfil"

# Dónde sirve T-320 la foto propia (`accounts:foto`). Mientras esa ruta no esté registrada,
# `Picked.url` usa esta misma dirección; cuando exista, `reverse` da el mismo resultado.
OWN_URL = "/perfil/fotos/{}/"

# Clave de la sesión con la última foto elegida, para no repetirla (REQ-138).
SESSION_KEY = "foto_anterior"

# Límites de la subida (plan 017, "Fotos").
MAX_RAW_BYTES = 10 * 1024 * 1024
MAX_PIXELS = 50_000_000
MAX_SIDE = 1600
ALLOWED_FORMATS = ("JPEG", "PNG", "WEBP")
QUALITIES = range(90, 29, -5)
SMOOTHING_RADIUS = 4  # a cuántos niveles de entrada, como máximo, se mira a cada lado
SMOOTHING_WINDOW = 2  # y solo se promedian los que caen a 2 niveles de salida o menos
SLOT_CONSTRAINT = "accounts_photo_user_slot_unique"


class PhotoRejected(ValueError):
    """La foto no se puede guardar; el texto explica por qué y está listo para mostrarse."""


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
        try:
            return reverse("accounts:foto", args=[self.photo_id])
        except NoReverseMatch:
            return OWN_URL.format(self.photo_id)


def house_photo_path():
    return Path(settings.BASE_DIR) / "evaluon" / "static" / HOUSE_PHOTO


@lru_cache(maxsize=1)
def reference_histogram():
    """Histograma de 256 niveles de gris de la foto de la casa (una tupla, calculada una vez)."""
    with Image.open(house_photo_path()) as image:
        return tuple(image.convert("L").histogram())


# --- Elección (REQ-138) ----------------------------------------------------------------------


def pick_for(request):
    """La foto para el pedido: al azar entre las del usuario, sin repetir la anterior.

    Sin usuario o sin fotos propias, la de la casa. Se llama al servir la página, no desde el
    navegador: los sondeos no la tocan, así que no cambia mientras se está en la pantalla.
    """
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return Picked(photo_id=None, label=HOUSE_LABEL)
    ids = list(Photo.objects.filter(user=user).values_list("pk", flat=True))
    if not ids:
        return Picked(photo_id=None, label=HOUSE_LABEL)
    session = getattr(request, "session", None)
    previous = session.get(SESSION_KEY) if session is not None else None
    candidates = [pk for pk in ids if pk != previous] if len(ids) > 1 else ids
    chosen = random.choice(candidates)
    if session is not None and previous != chosen:
        session[SESSION_KEY] = chosen
    return Picked(photo_id=chosen, label=OWN_LABEL)


# --- Baja ------------------------------------------------------------------------------------


def remove(user, photo_id):
    """Borra de verdad una foto del usuario. `False` si no existe o es de otro."""
    deleted, _ = Photo.objects.filter(pk=photo_id, user=user).delete()
    return deleted > 0


# --- Subida (REQ-136, REQ-137) ---------------------------------------------------------------


def used_slots(user):
    """Las ranuras que el usuario ya ocupa."""
    return set(Photo.objects.filter(user=user).values_list("slot", flat=True))


def upload(user, file):
    """Ajusta y guarda una foto del usuario; devuelve la `Photo`. Rechaza con `PhotoRejected`.

    Cualquier usuario autenticado puede subir y quitar sus fotos, también el de lectura: no es
    una acción de decisión. Solo se guarda la foto ajustada; el original se descarta.
    """
    data = _read(file)
    if Photo.objects.filter(user=user).count() >= PHOTO_SLOTS:
        raise _full()
    content, width, height = _normalize(data)
    return _store(user, content, width, height)


def _full():
    return PhotoRejected(
        f"Ya tenés {PHOTO_SLOTS} fotos, el máximo. Para subir otra, quitá una antes."
    )


def _read(file):
    """Los bytes de lo subido; rechaza lo que pasa de 10 MiB sin leerlo entero."""
    if isinstance(file, (bytes, bytearray)):
        data = bytes(file)
    else:
        if hasattr(file, "seek"):
            file.seek(0)
        data = file.read(MAX_RAW_BYTES + 1)
    if len(data) > MAX_RAW_BYTES:
        raise PhotoRejected("La foto pesa más de 10 MiB. Elegí una más liviana.")
    return data


def _open(data):
    """Abre con Pillow solo si el contenido es JPEG, PNG o WebP y no declara demasiados píxeles."""
    try:
        image = Image.open(io.BytesIO(data), formats=ALLOWED_FORMATS)
    except UnidentifiedImageError:
        raise PhotoRejected(
            "El archivo no es una foto en un formato permitido. Subí una imagen JPEG, PNG o WebP."
        ) from None
    except Image.DecompressionBombError:
        raise _too_many_pixels() from None
    except (OSError, SyntaxError, ValueError, EOFError):
        raise _damaged() from None
    width, height = image.size
    if width * height > MAX_PIXELS:
        image.close()
        raise _too_many_pixels()
    return image


def _too_many_pixels():
    return PhotoRejected(
        f"La foto tiene demasiados píxeles (más de {MAX_PIXELS // 1_000_000} millones). "
        "Elegí una más chica."
    )


def _damaged():
    return PhotoRejected("La foto está dañada o incompleta. Probá con otra.")


def to_luminance(image):
    """Pasa a niveles de gris de 8 bits; lo transparente se compone antes sobre blanco."""
    if image.mode.startswith("I"):
        # Grises de 16 bits: se escalan a 8 en lugar de recortar a blanco.
        return image.convert("I").point(lambda value: value * (1 / 256)).convert("L")
    transparent = image.mode in ("RGBA", "LA", "PA", "RGBa", "La") or (
        "transparency" in image.info
    )
    if transparent:
        rgba = image.convert("RGBA")
        base = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        base.alpha_composite(rgba)
        return base.convert("L")
    return image.convert("L")


def tone_table(source, reference):
    """Tabla de 256 niveles que lleva el histograma `source` al de `reference`.

    Cada nivel va al nivel de la referencia que tiene la misma posición acumulada (en Python
    puro, con interpolación dentro del nivel). La tabla se suaviza con un promedio móvil que solo
    junta niveles de entrada cercanos Y que terminan a `SMOOTHING_WINDOW` niveles de salida o
    menos: así se alisan los escalones de redondeo sin achatar las partes empinadas, que son las
    de las fotos oscuras o saturadas que ocupan pocos niveles. Al final se fuerza que sea creciente.

    Límite conocido: una imagen casi lisa (desvío de entrada menor a 3 de 255, por ejemplo una
    foto en blanco o una niebla total) casi no tiene niveles que repartir y no alcanza el tono de
    la casa; no es una foto real y no se corrige.
    """
    total_source, total_reference = sum(source), sum(reference)
    if not total_source or not total_reference:
        return list(range(256))
    reference_cdf = []
    running = 0
    for count in reference:
        running += count
        reference_cdf.append(running / total_reference)
    raw = []
    before = 0
    level = 0
    for count in source:
        quantile = (before + count / 2) / total_source
        before += count
        while level < 255 and reference_cdf[level] < quantile:
            level += 1
        floor = reference_cdf[level - 1] if level else 0.0
        span = reference_cdf[level] - floor
        fraction = (quantile - floor) / span if span > 0 else 0.5
        raw.append(min(255.0, max(0.0, level - 0.5 + min(1.0, max(0.0, fraction)))))
    table = []
    for index in range(256):
        near = raw[max(0, index - SMOOTHING_RADIUS) : index + SMOOTHING_RADIUS + 1]
        close = [value for value in near if abs(value - raw[index]) <= SMOOTHING_WINDOW]
        rounded = int(round(sum(close) / len(close)))
        table.append(max(rounded, table[-1]) if table else rounded)
    return table


def _normalize(data):
    """De los bytes subidos a (JPEG ajustado, ancho, alto)."""
    image = _open(data)
    try:
        if image.format == "JPEG" and image.mode in ("RGB", "L"):
            image.draft("L", (MAX_SIDE, MAX_SIDE))  # decodifica ya reducida: ahorra memoria
        image = ImageOps.exif_transpose(image)
        gray = to_luminance(image)
    except Image.DecompressionBombError:
        raise _too_many_pixels() from None
    except (OSError, SyntaxError, ValueError, EOFError):
        raise _damaged() from None
    gray.thumbnail((MAX_SIDE, MAX_SIDE), Image.Resampling.LANCZOS)  # no amplía
    gray = gray.point(tone_table(gray.histogram(), reference_histogram()))
    # Una imagen nueva, solo con los píxeles: ninguna información de la original (comentario,
    # perfil de color, EXIF, texto) pasa al JPEG guardado (P4).
    gray = Image.frombytes("L", gray.size, gray.tobytes())
    for quality in QUALITIES:
        buffer = io.BytesIO()
        gray.save(buffer, "JPEG", quality=quality, optimize=True)
        if buffer.tell() < PHOTO_MAX_BYTES:
            return buffer.getvalue(), gray.width, gray.height
    raise PhotoRejected(
        "No se pudo dejar la foto con un tamaño menor a 2 MiB. Elegí una más simple o más chica."
    )


def _store(user, content, width, height):
    """Guarda en la primera ranura libre. Si otra subida ganó esa ranura (restricción única de la
    base), reintenta con la siguiente libre; si ya no queda ninguna, pide quitar una."""
    for _ in range(PHOTO_SLOTS + 1):
        taken = used_slots(user)
        free = [slot for slot in range(PHOTO_SLOTS) if slot not in taken]
        if not free:
            raise _full()
        try:
            with transaction.atomic():
                return Photo.objects.create(
                    user=user,
                    slot=free[0],
                    content=content,
                    sha256=hashlib.sha256(content).hexdigest(),
                    width=width,
                    height=height,
                    size=len(content),
                )
        except IntegrityError as error:
            if not _is_slot_conflict(error):
                raise  # otra restricción (por ejemplo el tope de tamaño): no es una carrera
    raise PhotoRejected(
        "No se pudo guardar la foto porque hubo otras subidas a la vez. Probá de nuevo."
    )


def _is_slot_conflict(error):
    """Si el error de la base es el de la ranura única (otra subida ganó esa ranura)."""
    diag = getattr(error.__cause__, "diag", None)
    return getattr(diag, "constraint_name", None) == SLOT_CONSTRAINT
