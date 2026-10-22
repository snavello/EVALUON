"""Fotos personales: normalización, subida y elección (T-319; REQ-136, REQ-137, REQ-138;
ADR-0073; P4).

Todas las imágenes se generan en memoria con Pillow: ninguna foto entra al repositorio ni a las
pruebas. Los usuarios son sintéticos. El criterio numérico de REQ-137 (brillo medio y contraste de
dos fotos muy distintas, 10 % o menos; meta de implementación, 5 %) se mide con dos imágenes
sintéticas: una oscura y saturada, otra clara y fría.
"""

import hashlib
import io
import random
import struct
import zlib

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory
from PIL import Image

from evaluon.accounts import photos
from evaluon.accounts.models import PHOTO_MAX_BYTES, PHOTO_SLOTS, Photo, Role
from tests.conftest import TEST_PASSWORD

GOAL = 0.05
LIMIT = 0.10


# --- Ayudas ----------------------------------------------------------------------------------


def make_user(username="con-fotos", role=Role.READ):
    return get_user_model().objects.create_user(
        username=username, password=TEST_PASSWORD, role=role
    )


def make_photo(user, slot=0, content=b"bytes-de-prueba"):
    return Photo.objects.create(
        user=user,
        slot=slot,
        content=content,
        sha256=hashlib.sha256(content).hexdigest(),
        width=10,
        height=10,
        size=len(content),
    )


def noisy_image(size, centre, spread, seed):
    """Imagen RGB con colores al azar (semilla fija) alrededor de `centre`."""
    rng = random.Random(seed)
    clip = lambda value: max(0, min(255, int(value)))  # noqa: E731
    pixels = [
        tuple(clip(rng.gauss(c, s)) for c, s in zip(centre, spread))
        for _ in range(size[0] * size[1])
    ]
    image = Image.new("RGB", size)
    image.putdata(pixels)
    return image


def dark_saturated():
    return noisy_image((240, 180), (70, 8, 25), (35, 10, 18), seed=1)


def light_cool():
    return noisy_image((240, 180), (185, 222, 246), (28, 22, 12), seed=2)


def encode(image, fmt="PNG", **kwargs):
    buffer = io.BytesIO()
    image.save(buffer, fmt, **kwargs)
    return buffer.getvalue()


def stored(photo):
    return Image.open(io.BytesIO(bytes(photo.content)))


def statistics(photo):
    """Brillo medio y contraste (desvío) de la foto guardada, de 0 a 255."""
    histogram = stored(photo).convert("L").histogram()
    total = sum(histogram)
    mean = sum(level * count for level, count in enumerate(histogram)) / total
    variance = sum(count * (level - mean) ** 2 for level, count in enumerate(histogram)) / total
    return mean, variance**0.5


def relative_difference(a, b):
    return abs(a - b) / max(a, b)


def header_only_png(width, height, data=b""):
    """PNG con solo el encabezado y datos mínimos: declara las medidas que se pidan sin traer los
    píxeles (una bomba si son enormes; una imagen rota si `data` no es zlib válido)."""

    def chunk(kind, data):
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    header = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", data or zlib.compress(b""))
        + chunk(b"IEND", b"")
    )


def request_for(user, session=None):
    request = RequestFactory().get("/")
    request.user = user
    request.session = {} if session is None else session
    return request


# --- REQ-137: el tono ------------------------------------------------------------------------


@pytest.mark.django_db
def test_two_very_different_photos_end_with_the_same_brightness_and_contrast():
    """REQ-137: una foto oscura y saturada y otra clara y fría quedan en blanco y negro, con
    brillo medio y contraste que difieren 10 % o menos (meta: 5 %), y cerca de los de la casa."""
    user = make_user()
    dark = photos.upload(user, io.BytesIO(encode(dark_saturated())))
    light = photos.upload(user, io.BytesIO(encode(light_cool())))

    for photo in (dark, light):
        assert stored(photo).mode == "L"
        assert stored(photo).format == "JPEG"

    (mean_d, contrast_d), (mean_l, contrast_l) = statistics(dark), statistics(light)
    brightness_diff = relative_difference(mean_d, mean_l)
    contrast_diff = relative_difference(contrast_d, contrast_l)
    print(
        f"REQ-137 entre las dos: brillo {mean_d:.1f} vs {mean_l:.1f} "
        f"(diferencia {brightness_diff:.2%}); contraste {contrast_d:.1f} vs {contrast_l:.1f} "
        f"(diferencia {contrast_diff:.2%})"
    )
    assert brightness_diff <= LIMIT
    assert contrast_diff <= LIMIT

    house = photos.reference_histogram()
    total = sum(house)
    house_mean = sum(level * count for level, count in enumerate(house)) / total
    house_contrast = (
        sum(count * (level - house_mean) ** 2 for level, count in enumerate(house)) / total
    ) ** 0.5
    for mean, contrast in ((mean_d, contrast_d), (mean_l, contrast_l)):
        brightness_vs_house = relative_difference(mean, house_mean)
        contrast_vs_house = relative_difference(contrast, house_contrast)
        print(
            f"REQ-137 contra la casa: brillo {mean:.1f} vs {house_mean:.1f} "
            f"({brightness_vs_house:.2%}); contraste {contrast:.1f} vs {house_contrast:.1f} "
            f"({contrast_vs_house:.2%})"
        )
        assert brightness_vs_house <= LIMIT
        assert contrast_vs_house <= LIMIT


@pytest.mark.django_db
def test_the_tone_meets_the_implementation_goal():
    """REQ-137: la meta de implementación es 5 %, la mitad del máximo de la spec."""
    user = make_user()
    dark = photos.upload(user, io.BytesIO(encode(dark_saturated())))
    light = photos.upload(user, io.BytesIO(encode(light_cool())))
    assert relative_difference(statistics(dark)[0], statistics(light)[0]) <= GOAL
    assert relative_difference(statistics(dark)[1], statistics(light)[1]) <= GOAL


def test_the_conversion_to_luminance_composes_transparency_on_white():
    """REQ-137: lo transparente se compone sobre blanco antes de pasar a blanco y negro."""
    image = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
    image.putpixel((0, 0), (0, 0, 0, 255))
    result = photos.to_luminance(image)
    assert result.mode == "L"
    assert result.getpixel((1, 1)) == 255
    assert result.getpixel((0, 0)) == 0

    palette = Image.new("P", (2, 2), 0)
    palette.putpalette([0, 0, 0] * 256)
    palette.info["transparency"] = 0
    assert photos.to_luminance(palette).getpixel((0, 0)) == 255


def test_the_mapping_table_is_smooth_and_never_goes_down():
    """REQ-137: la tabla de 256 niveles que ajusta el histograma es creciente y suave."""
    histogram = [0] * 256
    histogram[10] = 500
    histogram[200] = 500
    table = photos.tone_table(histogram, photos.reference_histogram())
    assert len(table) == 256
    assert all(0 <= value <= 255 for value in table)
    assert all(a <= b for a, b in zip(table, table[1:]))


def test_16_bit_grays_are_scaled_to_8_bits_instead_of_clipped():
    """REQ-137: un PNG de 16 bits por canal se lleva a 8 bits sin recortar a blanco."""
    gradient = Image.new("I;16", (256, 8))
    gradient.putdata([x * 257 for _ in range(8) for x in range(256)])
    gray = photos.to_luminance(gradient)
    assert gray.mode == "L"
    mean = sum(level * count for level, count in enumerate(gray.histogram())) / (256 * 8)
    assert 120 <= mean <= 135


@pytest.mark.django_db
def test_a_16_bit_png_can_be_uploaded():
    """REQ-137: la subida de un PNG de 16 bits llega al final."""
    gradient = Image.new("I;16", (256, 8))
    gradient.putdata([x * 257 for _ in range(8) for x in range(256)])
    assert photos.upload(make_user(), io.BytesIO(encode(gradient))).size > 0


# --- REQ-137: lo que se guarda ---------------------------------------------------------------


@pytest.mark.django_db
def test_the_stored_jpeg_has_no_exif_nor_location():
    """REQ-136, P4: el JPEG guardado no trae EXIF (se pierde la ubicación)."""
    image = dark_saturated()
    exif = Image.Exif()
    exif[0x010F] = "Camara sintetica"
    exif[0x8825] = {1: "S", 2: (34.0, 36.0, 0.0), 3: "W", 4: (58.0, 22.0, 0.0)}
    raw = encode(image, "JPEG", exif=exif)
    assert b"Exif" in raw

    photo = photos.upload(make_user(), io.BytesIO(raw))

    assert b"Exif" not in bytes(photo.content)
    assert len(stored(photo).getexif()) == 0
    assert "exif" not in stored(photo).info


@pytest.mark.django_db
def test_the_orientation_is_corrected_before_saving():
    """REQ-137: una foto con orientación EXIF 6 (girada) se guarda ya derecha."""
    image = noisy_image((100, 50), (120, 120, 120), (30, 30, 30), seed=3)
    exif = Image.Exif()
    exif[0x0112] = 6
    photo = photos.upload(make_user(), io.BytesIO(encode(image, "JPEG", exif=exif)))
    assert (photo.width, photo.height) == (50, 100)
    assert stored(photo).size == (50, 100)


@pytest.mark.django_db
def test_a_big_photo_is_reduced_to_1600_and_a_small_one_is_not_enlarged():
    """REQ-137: el lado mayor queda en 1600 px como mucho; lo chico no se amplía."""
    user = make_user()
    big = photos.upload(user, io.BytesIO(encode(Image.new("L", (3000, 2000), 128), "PNG")))
    assert stored(big).size == (1600, 1067)
    small = photos.upload(user, io.BytesIO(encode(Image.new("L", (400, 300), 128), "PNG")))
    assert stored(small).size == (400, 300)
    assert (small.width, small.height) == (400, 300)


@pytest.mark.django_db
def test_the_saved_row_carries_size_and_digest_of_what_is_stored():
    """REQ-136: se guardan el tamaño y la huella SHA-256 del contenido ajustado."""
    photo = photos.upload(make_user(), io.BytesIO(encode(dark_saturated())))
    photo.refresh_from_db()
    content = bytes(photo.content)
    assert photo.size == len(content)
    assert photo.sha256 == hashlib.sha256(content).hexdigest()
    assert 0 < photo.size < PHOTO_MAX_BYTES


@pytest.mark.django_db
def test_a_django_uploaded_file_is_accepted_whatever_its_name():
    """REQ-136: se decide por el contenido, no por la extensión ni por el tipo declarado."""
    raw = encode(dark_saturated(), "PNG")
    file = SimpleUploadedFile("recuerdo.txt", raw, content_type="text/plain")
    assert stored(photos.upload(make_user(), file)).format == "JPEG"
    for fmt in ("JPEG", "WEBP"):
        assert photos.upload(make_user(f"otro-{fmt}"), io.BytesIO(encode(light_cool(), fmt)))


@pytest.mark.django_db
def test_the_stored_size_is_below_2_mib_even_with_noise(monkeypatch):
    """REQ-136: la calidad baja hasta quedar por debajo del tope; el resultado cabe en la base."""
    noise = Image.frombytes("L", (1200, 1200), random.Random(4).randbytes(1200 * 1200))
    raw = encode(noise, "PNG")
    user = make_user()
    normal = photos.upload(user, io.BytesIO(raw))
    assert normal.size < PHOTO_MAX_BYTES

    limit = normal.size // 2
    monkeypatch.setattr(photos, "PHOTO_MAX_BYTES", limit)
    smaller = photos.upload(user, io.BytesIO(raw))
    assert smaller.size < limit < normal.size


@pytest.mark.django_db
def test_a_photo_that_cannot_fit_is_rejected_with_a_clear_message(monkeypatch):
    """REQ-136: si ni con la calidad más baja cabe, se rechaza con un mensaje claro."""
    monkeypatch.setattr(photos, "PHOTO_MAX_BYTES", 100)
    user = make_user()
    with pytest.raises(photos.PhotoRejected) as error:
        photos.upload(user, io.BytesIO(encode(dark_saturated())))
    assert "tamaño" in str(error.value).lower()
    assert Photo.objects.count() == 0


def test_the_reference_histogram_is_reused_by_every_upload(db):
    """REQ-137: el histograma de la casa se calcula una sola vez para todas las subidas."""
    photos.reference_histogram.cache_clear()
    user = make_user()
    photos.upload(user, io.BytesIO(encode(dark_saturated())))
    photos.upload(user, io.BytesIO(encode(light_cool())))
    assert photos.reference_histogram.cache_info().misses == 1


# --- Rechazos --------------------------------------------------------------------------------


@pytest.mark.django_db
def test_a_corrupt_image_is_rejected_with_a_clear_message():
    """REQ-136: una imagen cortada o con datos rotos se rechaza y no deja nada guardado."""
    raw = encode(dark_saturated(), "JPEG")
    user = make_user()
    with pytest.raises(photos.PhotoRejected) as truncated:
        photos.upload(user, io.BytesIO(raw[: len(raw) // 2]))
    assert "dañada" in str(truncated.value)
    broken = header_only_png(50, 50, b"no son datos de una imagen" * 5)
    with pytest.raises(photos.PhotoRejected) as bad_png:
        photos.upload(user, io.BytesIO(broken))
    assert "dañada" in str(bad_png.value)
    assert Photo.objects.count() == 0


@pytest.mark.django_db
def test_a_format_that_is_not_allowed_is_rejected_by_its_content():
    """REQ-136: solo JPEG, PNG o WebP; se mira el contenido, no el nombre del archivo."""
    user = make_user()
    gif = SimpleUploadedFile("foto.jpg", encode(light_cool().convert("P"), "GIF"))
    with pytest.raises(photos.PhotoRejected) as error:
        photos.upload(user, gif)
    assert "JPEG, PNG o WebP" in str(error.value)
    for junk in (b"%PDF-1.4 no es una foto", b"texto cualquiera", b""):
        with pytest.raises(photos.PhotoRejected):
            photos.upload(user, io.BytesIO(junk))
    assert Photo.objects.count() == 0


@pytest.mark.django_db
def test_a_pixel_bomb_is_rejected_without_decoding_it():
    """REQ-136: una imagen que declara demasiados píxeles se rechaza al abrirla."""
    user = make_user()
    for width, height in ((9000, 9000), (60000, 60000)):
        with pytest.raises(photos.PhotoRejected) as error:
            photos.upload(user, io.BytesIO(header_only_png(width, height)))
        assert "píxeles" in str(error.value)
    assert Photo.objects.count() == 0


@pytest.mark.django_db
def test_a_file_over_10_mib_is_rejected_before_any_processing(monkeypatch):
    """REQ-136: lo que pasa de 10 MiB sin procesar se rechaza sin abrirlo con Pillow."""

    def must_not_open(*args, **kwargs):
        raise AssertionError("no debía abrirse")

    monkeypatch.setattr(photos.Image, "open", must_not_open)
    big = b"\xff\xd8\xff" + b"0" * (10 * 1024 * 1024)
    with pytest.raises(photos.PhotoRejected) as error:
        photos.upload(make_user(), io.BytesIO(big))
    assert "10 MiB" in str(error.value)


@pytest.mark.django_db
def test_the_11th_photo_is_rejected_asking_to_remove_one():
    """REQ-136: con 10 fotos, la 11.ª se rechaza y pide quitar una antes."""
    user = make_user()
    for slot in range(PHOTO_SLOTS):
        make_photo(user, slot)
    with pytest.raises(photos.PhotoRejected) as error:
        photos.upload(user, io.BytesIO(encode(dark_saturated())))
    assert "quitá una" in str(error.value)
    assert Photo.objects.filter(user=user).count() == 10


# --- Ranuras ---------------------------------------------------------------------------------


@pytest.mark.django_db
def test_upload_takes_the_first_free_slot():
    """REQ-136: se usa la primera ranura libre; al quitar una, la siguiente subida la ocupa."""
    user = make_user()
    raw = encode(dark_saturated())
    taken = [photos.upload(user, io.BytesIO(raw)).slot for _ in range(3)]
    assert taken == [0, 1, 2]
    removed = Photo.objects.get(user=user, slot=1)
    assert photos.remove(user, removed.pk)
    assert photos.upload(user, io.BytesIO(raw)).slot == 1
    assert photos.upload(user, io.BytesIO(raw)).slot == 3


@pytest.mark.django_db
def test_two_uploads_that_pick_the_same_slot_do_not_fail_nor_overwrite(monkeypatch):
    """REQ-136: si otra subida ganó la ranura (restricción única de la base), se reintenta con
    la siguiente libre y las dos fotos quedan guardadas."""
    user = make_user()
    make_photo(user, 0, b"ganadora")
    real = photos.used_slots
    calls = []

    def stale(target):
        calls.append(1)
        return set() if len(calls) == 1 else real(target)

    monkeypatch.setattr(photos, "used_slots", stale)
    photo = photos.upload(user, io.BytesIO(encode(dark_saturated())))
    assert photo.slot == 1
    assert len(calls) >= 2
    assert bytes(Photo.objects.get(user=user, slot=0).content) == b"ganadora"
    assert Photo.objects.filter(user=user).count() == 2


@pytest.mark.django_db
def test_a_lost_race_for_the_last_slot_is_rejected_with_a_clear_message(monkeypatch):
    """REQ-136: si la carrera la gana otra subida y ya no quedan ranuras, se pide quitar una."""
    user = make_user()
    for slot in range(PHOTO_SLOTS - 1):
        make_photo(user, slot)
    state = {"first": True}
    real = photos.used_slots

    def stale(target):
        if state["first"]:
            # Mientras esta subida decide, otra se queda con la última ranura.
            state["first"] = False
            make_photo(target, PHOTO_SLOTS - 1, b"ganadora")
            return set(range(PHOTO_SLOTS - 1))
        return real(target)

    monkeypatch.setattr(photos, "used_slots", stale)
    with pytest.raises(photos.PhotoRejected) as error:
        photos.upload(user, io.BytesIO(encode(dark_saturated())))
    assert "quitá una" in str(error.value)
    assert Photo.objects.filter(user=user).count() == 10


# --- Quitar ----------------------------------------------------------------------------------


@pytest.mark.django_db
def test_remove_deletes_for_real_and_only_for_the_owner():
    """REQ-136: quitar es un borrado real y solo lo puede hacer el dueño."""
    owner, other = make_user("dueño"), make_user("ajeno")
    mine = make_photo(owner, 0)
    assert photos.remove(other, mine.pk) is False
    assert Photo.objects.filter(pk=mine.pk).exists()
    assert photos.remove(owner, mine.pk) is True
    assert not Photo.objects.filter(pk=mine.pk).exists()
    assert photos.remove(owner, mine.pk) is False


# --- REQ-138: la elección --------------------------------------------------------------------


def test_without_a_user_the_house_photo_is_used_and_the_database_is_not_touched():
    """REQ-136: sin sesión de usuario se muestra la foto de la casa, sin consultar la base."""
    request = RequestFactory().get("/")
    picked = photos.pick_for(request)
    assert picked.photo_id is None
    assert picked.label == "Foto de la casa"


@pytest.mark.django_db
def test_a_user_without_photos_gets_the_house_photo():
    """REQ-136: sin fotos propias se muestra la de la casa."""
    picked = photos.pick_for(request_for(make_user()))
    assert picked.photo_id is None
    assert picked.label == "Foto de la casa"
    assert picked.url.endswith("diseno/casa/biblioratos-bn.jpg")


@pytest.mark.django_db
def test_with_three_photos_successive_requests_never_repeat_the_previous():
    """REQ-138: con 3 fotos, cada pedido elige una distinta de la anterior, y las tres salen."""
    user = make_user()
    ids = {make_photo(user, slot).pk for slot in range(3)}
    session = {}
    previous = None
    seen = set()
    for _ in range(60):
        picked = photos.pick_for(request_for(user, session))
        assert picked.photo_id in ids
        assert picked.photo_id != previous
        assert picked.label == "Foto de su perfil"
        seen.add(picked.photo_id)
        previous = picked.photo_id
    assert seen == ids


@pytest.mark.django_db
def test_with_one_photo_it_is_always_that_one():
    """REQ-138: con una sola foto no hay otra que elegir."""
    user = make_user()
    only = make_photo(user, 0)
    session = {}
    for _ in range(3):
        assert photos.pick_for(request_for(user, session)).photo_id == only.pk


@pytest.mark.django_db
def test_other_users_photos_are_never_picked():
    """REQ-136, P4: la elección mira solo las fotos del propio usuario."""
    mine, other = make_user("mía"), make_user("ajena")
    make_photo(other, 0)
    make_photo(other, 1)
    assert photos.pick_for(request_for(mine)).photo_id is None
    own = make_photo(mine, 0)
    for _ in range(10):
        assert photos.pick_for(request_for(mine, {})).photo_id == own.pk


@pytest.mark.django_db
def test_a_previous_photo_that_was_removed_does_not_get_in_the_way():
    """REQ-138: si la anterior ya no existe, se elige entre las que quedan."""
    user = make_user()
    keep, gone = make_photo(user, 0), make_photo(user, 1)
    session = {}
    photos.pick_for(request_for(user, session))
    session[photos.SESSION_KEY] = gone.pk
    gone.delete()
    assert photos.pick_for(request_for(user, session)).photo_id == keep.pk


@pytest.mark.django_db
def test_the_choice_does_not_load_the_image_bytes(django_assert_num_queries):
    """REQ-138: elegir es una sola consulta de ids; no trae el contenido de las fotos."""
    user = make_user()
    for slot in range(3):
        make_photo(user, slot, b"x" * 1000)
    request = request_for(user)
    with django_assert_num_queries(1) as context:
        photos.pick_for(request)
    assert "content" not in context.captured_queries[0]["sql"]


@pytest.mark.django_db
def test_the_url_of_an_own_photo_works_before_and_after_the_route_exists():
    """REQ-136: la dirección de una foto propia es /perfil/fotos/<id>/; T-320 registra la ruta
    `accounts:foto` y esa misma dirección sigue valiendo. Aquí no se depende de la ruta."""
    user = make_user()
    photo = make_photo(user, 0)
    picked = photos.pick_for(request_for(user))
    assert picked.photo_id == photo.pk
    assert picked.url == f"/perfil/fotos/{photo.pk}/"
    assert photos.Picked(photo_id=None, label="x").url.endswith("biblioratos-bn.jpg")


# --- Verificación de T-319: tono con pocos niveles, metadatos JPEG y tope del reintento ----------


def house_gray():
    """La foto de la casa en grises y reducida: estructura real para derivar variantes."""
    with Image.open(photos.house_photo_path()) as house:
        gray = house.convert("L")
    gray.thumbnail((700, 700))
    return gray


def tinted(low, high, saturation, gamma=None):
    """La foto de la casa oscurecida (gamma), teñida entre dos colores y saturada."""
    from PIL import ImageEnhance, ImageOps

    gray = house_gray()
    if gamma:
        gray = gray.point([int(255 * (level / 255) ** gamma) for level in range(256)])
    return ImageEnhance.Color(ImageOps.colorize(gray, low, high)).enhance(saturation)


HOUSE_VARIANTS = {
    "roja saturada": lambda: tinted((20, 0, 0), (250, 60, 30), 1.8),
    "roja muy oscurecida": lambda: tinted((20, 0, 0), (250, 60, 30), 1.8, gamma=4.5),
    "azul oscura": lambda: tinted((0, 0, 10), (40, 80, 255), 2.0, gamma=3.0),
    "verde oscurecida": lambda: tinted((0, 10, 0), (60, 255, 40), 1.5, gamma=2.0),
    "naranja oscurecida": lambda: tinted((10, 5, 0), (255, 140, 20), 1.0, gamma=3.0),
    "clara y fria": lambda: tinted((120, 160, 200), (250, 255, 255), 1.0, gamma=0.5),
    "quemada": lambda: tinted((200, 200, 210), (255, 255, 255), 1.0),
    "alto contraste": lambda: tinted((0, 0, 0), (255, 255, 255), 1.0, gamma=0.7),
}


def histogram_statistics(histogram):
    total = sum(histogram)
    mean = sum(level * count for level, count in enumerate(histogram)) / total
    spread = (sum(c * (level - mean) ** 2 for level, c in enumerate(histogram)) / total) ** 0.5
    return mean, spread


def house_statistics():
    return histogram_statistics(photos.reference_histogram())


def narrow_histogram():
    """Una foto oscura y saturada: ocupa pocos niveles de gris (unos 75 de 256)."""
    return photos.to_luminance(HOUSE_VARIANTS["roja saturada"]()).histogram()


def mapped_statistics(histogram, table):
    """Brillo medio y contraste que resultan de aplicar `table` a `histogram`."""
    mapped = [0] * 256
    for level, count in enumerate(histogram):
        mapped[table[level]] += count
    return histogram_statistics(mapped)


@pytest.mark.django_db
@pytest.mark.parametrize("name", sorted(HOUSE_VARIANTS))
def test_photos_with_few_gray_levels_still_reach_the_tone_of_the_house(name):
    """REQ-137: fotos oscuras, teñidas o saturadas (pocos niveles de gris ocupados) quedan con
    brillo medio y contraste a 10 % o menos de los de la casa (el suavizado no achata el rango)."""
    photo = photos.upload(make_user(), io.BytesIO(encode(HOUSE_VARIANTS[name]())))
    mean, contrast = statistics(photo)
    house_mean, house_contrast = house_statistics()
    brightness_diff = relative_difference(mean, house_mean)
    contrast_diff = relative_difference(contrast, house_contrast)
    print(
        f"REQ-137 {name}: brillo {mean:.1f} ({brightness_diff:.2%}); "
        f"contraste {contrast:.1f} ({contrast_diff:.2%}) contra la casa"
    )
    assert brightness_diff <= LIMIT
    assert contrast_diff <= LIMIT


@pytest.mark.django_db
def test_a_dark_saturated_and_a_light_cool_photo_of_the_house_end_close_to_each_other():
    """REQ-137: entre la roja saturada y la clara y fría, brillo y contraste difieren 10 % o menos."""
    user = make_user()
    dark = photos.upload(user, io.BytesIO(encode(HOUSE_VARIANTS["roja saturada"]())))
    light = photos.upload(user, io.BytesIO(encode(HOUSE_VARIANTS["clara y fria"]())))
    assert relative_difference(statistics(dark)[0], statistics(light)[0]) <= LIMIT
    assert relative_difference(statistics(dark)[1], statistics(light)[1]) <= LIMIT


def test_the_mapping_table_keeps_the_range_of_a_narrow_histogram():
    """REQ-137: con un histograma que ocupa pocos niveles (una foto oscura), la tabla suavizada
    sigue dando el brillo y el contraste de la referencia: el suavizado no achata lo empinado."""
    narrow = narrow_histogram()
    table = photos.tone_table(narrow, photos.reference_histogram())
    assert all(a <= b for a, b in zip(table, table[1:]))
    mean, spread = mapped_statistics(narrow, table)
    house_mean, house_contrast = house_statistics()
    assert relative_difference(spread, house_contrast) <= 0.05
    assert relative_difference(mean, house_mean) <= 0.05


def flat_zones(size, top, bottom, noise, circles, seed, blur=2, blocks=()):
    """Imagen sintética con zonas planas: degradado vertical con ruido gaussiano, círculos de
    color liso, bloques opcionales (fracciones del ancho y alto) y desenfoque."""
    from PIL import ImageDraw, ImageFilter

    rng = random.Random(seed)
    width, height = size
    clip = lambda value: max(0, min(255, int(value)))  # noqa: E731
    pixels = []
    for row in range(height):
        base = [top[i] + (bottom[i] - top[i]) * row / (height - 1) for i in range(3)]
        pixels.extend(tuple(clip(rng.gauss(c, noise)) for c in base) for _ in range(width))
    image = Image.new("RGB", size)
    image.putdata(pixels)
    draw = ImageDraw.Draw(image)
    for low, high in circles:
        radius = rng.randint(height // 12, height // 5)
        x, y = rng.randint(0, width), rng.randint(0, height)
        colour = tuple(rng.randint(low[i], high[i]) for i in range(3))
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=colour)
    for colour, (x0, y0, x1, y1) in blocks:
        box = (int(x0 * width), int(y0 * height), int(x1 * width), int(y1 * height))
        draw.rectangle(box, fill=colour)
    return image.filter(ImageFilter.GaussianBlur(blur)) if blur else image


def _circles(n, low, high):
    return [(low, high)] * n


# Las imágenes 1, 2, 3, 5 y 6 del verificador (registro de T-319, «Segunda ronda», H-3), con su
# misma estructura: pocos niveles de gris muy repetidos. La 4 (casi lisa) es el límite documentado.
FLAT_ZONES = {
    "1 oscura y saturada": lambda: flat_zones(
        (300, 200), (40, 5, 20), (15, 5, 40), 8, _circles(14, (0, 0, 0), (110, 60, 110)), seed=1
    ),
    "2 clara y fria": lambda: flat_zones(
        (300, 200), (225, 235, 250), (200, 225, 245), 8,
        _circles(14, (150, 190, 225), (255, 255, 255)), seed=2,
    ),
    "3 alto contraste": lambda: flat_zones(
        (300, 200), (250, 250, 250), (250, 250, 250), 0, [], seed=3, blur=0,
        blocks=[((0, 0, 0), (0, 0, 0.1, 1)), ((0, 0, 0), (0.5, 0, 0.55, 1))],
    ),
    "5 muy oscura": lambda: flat_zones(
        (300, 200), (18, 18, 20), (10, 10, 14), 8, _circles(14, (0, 0, 0), (60, 50, 60)), seed=5
    ),
    "6 muy clara y quemada": lambda: flat_zones(
        (300, 200), (245, 245, 240), (250, 250, 245), 8,
        _circles(14, (160, 170, 170), (255, 255, 255)), seed=6,
    ),
}


@pytest.mark.django_db
@pytest.mark.parametrize("name", sorted(FLAT_ZONES))
def test_images_with_flat_zones_reach_the_tone_of_the_house(name):
    """REQ-137: imágenes con pocos niveles de gris muy repetidos (colores lisos, bloques, fondo
    casi negro) quedan a 10 % o menos de la casa en brillo medio y contraste."""
    photo = photos.upload(make_user(), io.BytesIO(encode(FLAT_ZONES[name]())))
    mean, contrast = statistics(photo)
    house_mean, house_contrast = house_statistics()
    brightness_diff = relative_difference(mean, house_mean)
    contrast_diff = relative_difference(contrast, house_contrast)
    print(
        f"REQ-137 {name}: brillo {mean:.1f} ({brightness_diff:.2%}); "
        f"contraste {contrast:.1f} ({contrast_diff:.2%}) contra la casa"
    )
    assert brightness_diff <= LIMIT
    assert contrast_diff <= LIMIT


@pytest.mark.django_db
def test_the_dark_and_the_light_image_with_flat_zones_end_close_to_each_other():
    """REQ-137: el par oscura (1) / clara (2) con zonas planas queda a 10 % o menos entre sí."""
    user = make_user()
    dark = photos.upload(user, io.BytesIO(encode(FLAT_ZONES["1 oscura y saturada"]())))
    light = photos.upload(user, io.BytesIO(encode(FLAT_ZONES["2 clara y fria"]())))
    assert relative_difference(statistics(dark)[0], statistics(light)[0]) <= LIMIT
    assert relative_difference(statistics(dark)[1], statistics(light)[1]) <= LIMIT


@pytest.mark.django_db
@pytest.mark.parametrize("name", sorted(HOUSE_VARIANTS))
def test_house_variants_keep_the_implementation_goal(name):
    """REQ-137: las 8 variantes derivadas de la casa siguen a 5 % o menos (la corrección lineal
    no las empeora)."""
    photo = photos.upload(make_user(), io.BytesIO(encode(HOUSE_VARIANTS[name]())))
    mean, contrast = statistics(photo)
    house_mean, house_contrast = house_statistics()
    assert relative_difference(mean, house_mean) <= GOAL
    assert relative_difference(contrast, house_contrast) <= GOAL


def test_a_smoothing_that_flattens_the_table_would_be_caught(monkeypatch):
    """REQ-137: si el suavizado fuera tan ancho que achata la tabla (radio 20 y ventana ancha),
    el test anterior falla: este test comprueba que lo detecta."""
    narrow = narrow_histogram()
    monkeypatch.setattr(photos, "SMOOTHING_RADIUS", 20)
    monkeypatch.setattr(photos, "SMOOTHING_WINDOW", 100)
    table = photos.tone_table(narrow, photos.reference_histogram())
    _, spread = mapped_statistics(narrow, table)
    assert relative_difference(spread, house_statistics()[1]) > 0.05


def jpeg_markers(content):
    """Los marcadores (segmentos) de un JPEG, hasta el comienzo de los datos."""
    markers, position = [], 2
    while position < len(content):
        assert content[position] == 0xFF
        marker = content[position + 1]
        markers.append(marker)
        if marker == 0xDA:
            break
        position += 2 + int.from_bytes(content[position + 2 : position + 4], "big")
    return markers


def with_segments(jpeg, *segments):
    """Inserta segmentos (marcador, datos) justo después del comienzo de un JPEG."""
    extra = b"".join(
        b"\xff" + bytes([marker]) + (len(data) + 2).to_bytes(2, "big") + data
        for marker, data in segments
    )
    return jpeg[:2] + extra + jpeg[2:]


@pytest.mark.django_db
def test_the_stored_jpeg_has_no_comment_xmp_icc_nor_exif():
    """REQ-136, P4: un JPEG con comentario, XMP, perfil ICC y EXIF se guarda sin ninguno de ellos:
    solo quedan los segmentos de la imagen (JFIF, tablas, cuadro y datos)."""
    exif = Image.Exif()
    exif[0x010F] = "Camara sintetica"
    raw = encode(dark_saturated(), "JPEG", exif=exif, icc_profile=b"perfil-icc-privado" * 3)
    raw = with_segments(
        raw,
        (0xFE, b"comentario-privado-777"),
        (0xE1, b"http://ns.adobe.com/xap/1.0/\x00<x:xmpmeta>autor-privado-xmp</x:xmpmeta>"),
    )
    assert b"comentario-privado-777" in raw and b"autor-privado-xmp" in raw

    photo = photos.upload(make_user(), io.BytesIO(raw))

    content = bytes(photo.content)
    for secret in (
        b"comentario-privado-777",
        b"autor-privado-xmp",
        b"perfil-icc-privado",
        b"Camara sintetica",
        b"Exif",
        b"xmpmeta",
        b"ICC_PROFILE",
    ):
        assert secret not in content
    allowed = {0xE0, 0xDB, 0xC0, 0xC2, 0xC4, 0xDA}  # JFIF, tablas, cuadro, Huffman, datos
    assert set(jpeg_markers(content)) <= allowed
    reopened = stored(photo)
    assert "comment" not in reopened.info and "icc_profile" not in reopened.info
    assert len(reopened.getexif()) == 0


@pytest.mark.django_db
def test_the_text_of_a_png_does_not_reach_the_stored_jpeg():
    """REQ-136, P4: el texto de un PNG tampoco pasa al JPEG guardado."""
    from PIL import PngImagePlugin

    meta = PngImagePlugin.PngInfo()
    meta.add_text("Comment", "texto-privado-png-555")
    photo = photos.upload(make_user(), io.BytesIO(encode(dark_saturated(), "PNG", pnginfo=meta)))
    assert b"texto-privado-png-555" not in bytes(photo.content)


@pytest.mark.django_db
def test_a_permanent_slot_conflict_ends_after_at_most_11_tries_with_a_clear_message(monkeypatch):
    """REQ-136: si la base siempre responde que la ranura está ocupada, no hay bucle infinito:
    termina en 11 vueltas o menos con el mensaje de las subidas a la vez."""
    user = make_user()
    make_photo(user, 0, b"ocupa")
    calls = []

    def stale(target):
        calls.append(1)
        if len(calls) > PHOTO_SLOTS + 1:  # tope propio: falla en lugar de colgarse
            pytest.fail("el reintento pasó de 11 vueltas: no está acotado")
        return set()

    monkeypatch.setattr(photos, "used_slots", stale)
    with pytest.raises(photos.PhotoRejected) as error:
        photos.upload(user, io.BytesIO(encode(dark_saturated())))
    assert len(calls) <= PHOTO_SLOTS + 1
    assert "otras subidas a la vez" in str(error.value)
    assert Photo.objects.filter(user=user).count() == 1


@pytest.mark.django_db
def test_an_integrity_error_that_is_not_the_slot_is_not_called_simultaneous_uploads(monkeypatch):
    """REQ-136: un error de la base que no es el de la ranura (aquí el tope de tamaño) se
    relanza: no se disfraza de «subidas a la vez» ni se reintenta."""
    from django.db import IntegrityError

    monkeypatch.setattr(photos, "_normalize", lambda data: (b"x" * (PHOTO_MAX_BYTES + 1), 10, 10))
    calls = []
    real = photos.used_slots
    monkeypatch.setattr(photos, "used_slots", lambda target: calls.append(1) or real(target))
    with pytest.raises(IntegrityError):
        photos.upload(make_user(), io.BytesIO(encode(dark_saturated())))
    assert len(calls) == 1
