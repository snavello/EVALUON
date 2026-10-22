"""«Mis fotos»: pantalla del perfil y servido privado de cada foto (T-320; REQ-136; ADR-0073; P4).

Las imágenes se generan en memoria con Pillow y los usuarios son sintéticos: ninguna foto entra
al repositorio. Se prueba que nadie ve la foto de otro (404), que sin sesión se va al ingreso, que la
undécima foto se rechaza pidiendo quitar una, que quitar libera la ranura y que el enlace del menú
aparece.
"""

import hashlib
import io
import re
from pathlib import Path

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles import finders
from django.core.files.uploadedfile import SimpleUploadedFile
from django.shortcuts import resolve_url
from django.test import Client
from django.urls import reverse
from PIL import Image

from evaluon.accounts import photos
from evaluon.accounts.models import PHOTO_SLOTS, Photo, Role
from tests.conftest import TEST_PASSWORD

pytestmark = pytest.mark.django_db

FOTOS = "accounts:fotos"
FOTO = "accounts:foto"
QUITAR = "accounts:foto_quitar"


# --- Ayudas ----------------------------------------------------------------------------------


def make_user(username, role=Role.READ):
    return get_user_model().objects.create_user(username=username, password=TEST_PASSWORD, role=role)


def log_in(client, user):
    assert client.login(username=user.username, password=TEST_PASSWORD)
    return client


def make_photo(user, slot=0, content=None):
    content = content or f"bytes-{user.pk}-{slot}".encode()
    return Photo.objects.create(
        user=user, slot=slot, content=content, sha256=hashlib.sha256(content).hexdigest(),
        width=10, height=10, size=len(content),
    )


def fill(user, count):
    return [make_photo(user, slot) for slot in range(count)]


def image_bytes(color=(120, 60, 30), size=(64, 48)):
    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, "PNG")
    return buffer.getvalue()


def upload_file(name="foto.png", data=None):
    return SimpleUploadedFile(name, data or image_bytes(), content_type="image/png")


def post_photo(client, **kwargs):
    return client.post(reverse(FOTOS), {"foto": upload_file(**kwargs)})


@pytest.fixture
def owner():
    return make_user("dueno")


@pytest.fixture
def stranger():
    return make_user("ajeno")


# --- Rutas -----------------------------------------------------------------------------------


def test_the_routes_exist_with_the_expected_addresses():
    """REQ-136: `accounts:foto` da `/perfil/fotos/<id>/`, la misma que usa `Picked.url`."""
    assert reverse(FOTOS) == "/perfil/fotos/"
    assert reverse(FOTO, args=[1]) == "/perfil/fotos/1/"
    assert reverse(QUITAR, args=[1]) == "/perfil/fotos/1/quitar/"
    assert photos.Picked(photo_id=1, label="x").url == reverse(FOTO, args=[1])


# --- Sin sesión ------------------------------------------------------------------------------


def test_without_a_session_every_route_goes_to_the_login(owner):
    """REQ-136, P4: sin sesión, ninguna ruta de fotos responde: se va al ingreso."""
    photo = make_photo(owner)
    client = Client()
    login = resolve_url(settings.LOGIN_URL)
    for response in (
        client.get(reverse(FOTOS)),
        client.get(reverse(FOTO, args=[photo.pk])),
        client.post(reverse(FOTOS), {"foto": upload_file()}),
        client.post(reverse(QUITAR, args=[photo.pk])),
    ):
        assert response.status_code == 302
        assert response["Location"].startswith(login)
    assert Photo.objects.filter(pk=photo.pk).exists()


# --- Servido privado -------------------------------------------------------------------------


def test_the_owner_gets_the_bytes_with_private_cache_and_the_hash_as_etag(client, owner):
    """REQ-136, P4: el dueño recibe la foto, con `Cache-Control: private` y ETag con la huella."""
    photo = make_photo(owner, content=b"\xff\xd8contenido-de-prueba")
    log_in(client, owner)
    response = client.get(reverse(FOTO, args=[photo.pk]))
    assert response.status_code == 200
    assert response.content == b"\xff\xd8contenido-de-prueba"
    assert response["Content-Type"] == "image/jpeg"
    assert "private" in response["Cache-Control"]
    assert "public" not in response["Cache-Control"]
    assert response["ETag"] == f'"{photo.sha256}"'
    assert response["X-Content-Type-Options"] == "nosniff"


def test_a_repeated_request_with_the_etag_gets_304(client, owner):
    """REQ-136: con `If-None-Match` igual a la huella responde 304 sin cuerpo."""
    photo = make_photo(owner)
    log_in(client, owner)
    response = client.get(reverse(FOTO, args=[photo.pk]), headers={"If-None-Match": f'"{photo.sha256}"'})
    assert response.status_code == 304
    assert response.content == b""
    other = client.get(reverse(FOTO, args=[photo.pk]), headers={"If-None-Match": '"otra"'})
    assert other.status_code == 200


def test_another_user_gets_404_for_a_photo_that_is_not_theirs(client, owner, stranger):
    """REQ-136, P4: ningún otro usuario ve la foto; recibe 404, también uno con otro rol."""
    photo = make_photo(owner)
    for other in (stranger, make_user("escritor", Role.READ_WRITE)):
        log_in(client, other)
        response = client.get(reverse(FOTO, args=[photo.pk]))
        assert response.status_code == 404
        assert b"bytes-" not in response.content
        client.logout()


def test_a_photo_that_does_not_exist_gets_404(client, owner):
    """REQ-136: un identificador inexistente da 404."""
    log_in(client, owner)
    assert client.get(reverse(FOTO, args=[999999])).status_code == 404


def test_the_photo_route_only_answers_get(client, owner):
    """REQ-136: la ruta de servir no acepta POST."""
    photo = make_photo(owner)
    log_in(client, owner)
    assert client.post(reverse(FOTO, args=[photo.pk])).status_code == 405


# --- La pantalla -----------------------------------------------------------------------------


def test_the_page_lists_only_my_photos_through_the_private_route(client, owner, stranger):
    """REQ-136, P4: la pantalla muestra mis fotos por la ruta privada, nunca las ajenas ni `data:`."""
    mine = fill(owner, 3)
    theirs = fill(stranger, 2)
    log_in(client, owner)
    response = client.get(reverse(FOTOS))
    assert response.status_code == 200
    html = response.content.decode()
    for photo in mine:
        assert f'src="{reverse(FOTO, args=[photo.pk])}"' in html
    for photo in theirs:
        assert reverse(FOTO, args=[photo.pk]) not in html
    assert "data:" not in html
    assert "Mis fotos" in html


def test_the_page_has_ten_slots_with_one_to_add_and_free_places(client, owner):
    """REQ-136: hasta 10 ranuras; con 3 fotos hay 3 llenas, 1 para subir y 6 vacías."""
    fill(owner, 3)
    log_in(client, owner)
    html = client.get(reverse(FOTOS)).content.decode()
    assert len(re.findall(r'class="slot"', html)) == 3
    assert len(re.findall(r'class="slot empty"', html)) == PHOTO_SLOTS - 3 - 1
    assert "7 lugares libres" in html
    assert 'type="file"' in html and 'name="foto"' in html
    assert 'enctype="multipart/form-data"' in html


def test_with_ten_photos_the_page_asks_to_remove_one_before(client, owner):
    """REQ-136: con 10 fotos no hay formulario de subida y el mensaje pide quitar una antes."""
    fill(owner, PHOTO_SLOTS)
    log_in(client, owner)
    html = client.get(reverse(FOTOS)).content.decode()
    assert len(re.findall(r'class="slot"', html)) == PHOTO_SLOTS
    assert 'type="file"' not in html
    assert "quitá una antes" in html


def test_without_photos_the_page_says_the_house_photo_is_shown(client, owner):
    """REQ-136: sin fotos propias se avisa que se muestra la foto de la casa."""
    log_in(client, owner)
    html = client.get(reverse(FOTOS)).content.decode()
    assert "foto de la casa" in html
    assert "como la subió" not in html.lower()  # D-6 del plan: sin comparación


def test_the_page_has_no_inline_style_script_or_hex_and_loads_its_stylesheet(client, owner):
    """El proyecto no admite estilos ni scripts en línea; el color sale de tokens."""
    fill(owner, 2)
    log_in(client, owner)
    html = client.get(reverse(FOTOS)).content.decode()
    assert " style=" not in html
    assert not re.search(r"<script(?![^>]*\bsrc=)", html)
    assert not re.search(r"\son[a-z]+=", html)
    assert "accounts/fotos.css" in html
    css = Path(finders.find("accounts/fotos.css")).read_text(encoding="utf-8")
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", css)
    assert "rgb(" not in css and "rgba(" not in css


# --- Subir -----------------------------------------------------------------------------------


def test_uploading_stores_the_photo_and_goes_back_to_the_page(client, owner):
    """REQ-136: subir una foto válida la guarda para el usuario y vuelve a la pantalla."""
    log_in(client, owner)
    response = post_photo(client)
    assert response.status_code == 302 and response["Location"].startswith(reverse(FOTOS))
    assert Photo.objects.filter(user=owner).count() == 1
    page = client.get(response["Location"])
    assert "Foto subida" in page.content.decode()


def test_the_eleventh_photo_is_rejected_asking_to_remove_one(client, owner):
    """REQ-136: con 10 fotos, la 11.ª no se guarda y se pide quitar una antes."""
    fill(owner, PHOTO_SLOTS)
    log_in(client, owner)
    response = post_photo(client)
    assert response.status_code == 200
    assert "quitá una" in response.content.decode()
    assert Photo.objects.filter(user=owner).count() == PHOTO_SLOTS


def test_a_rejected_file_shows_the_message_of_the_error(client, owner):
    """REQ-136: un archivo que no es imagen se rechaza y se muestra el texto del error."""
    log_in(client, owner)
    response = client.post(reverse(FOTOS), {"foto": upload_file("a.png", b"esto no es una imagen")})
    assert response.status_code == 200
    with pytest.raises(photos.PhotoRejected) as error:
        photos.upload(owner, io.BytesIO(b"esto no es una imagen"))
    assert str(error.value) in response.content.decode().replace("&#x27;", "'")
    assert not Photo.objects.filter(user=owner).exists()


def test_posting_without_a_file_shows_a_clear_message(client, owner):
    """REQ-136: enviar el formulario sin archivo no rompe: avisa que falta elegir una foto."""
    log_in(client, owner)
    response = client.post(reverse(FOTOS), {})
    assert response.status_code == 200
    assert "Elija una foto" in response.content.decode()
    assert not Photo.objects.filter(user=owner).exists()


def test_the_uploaded_photo_is_served_to_its_owner_only(client, owner, stranger):
    """REQ-136, P4: lo subido se sirve al dueño como JPEG y al otro usuario le da 404."""
    log_in(client, owner)
    post_photo(client)
    photo = Photo.objects.get(user=owner)
    own = client.get(reverse(FOTO, args=[photo.pk]))
    assert own.status_code == 200 and own["Content-Type"] == "image/jpeg"
    assert Image.open(io.BytesIO(own.content)).format == "JPEG"
    other = log_in(Client(), stranger)
    assert other.get(reverse(FOTO, args=[photo.pk])).status_code == 404


def test_the_get_of_the_page_does_not_change_anything(client, owner):
    """REQ-136: ver la pantalla no crea ni borra fotos."""
    fill(owner, 2)
    log_in(client, owner)
    client.get(reverse(FOTOS))
    assert Photo.objects.filter(user=owner).count() == 2


# --- Quitar ----------------------------------------------------------------------------------


def test_removing_frees_the_slot_and_a_new_upload_takes_it(client, owner):
    """REQ-136: quitar borra la foto, deja libre la ranura y permite subir otra con 10 fotos antes."""
    made = fill(owner, PHOTO_SLOTS)
    log_in(client, owner)
    response = client.post(reverse(QUITAR, args=[made[4].pk]))
    assert response.status_code == 302 and response["Location"].startswith(reverse(FOTOS))
    assert not Photo.objects.filter(pk=made[4].pk).exists()
    assert Photo.objects.filter(user=owner).count() == PHOTO_SLOTS - 1
    assert post_photo(client).status_code == 302
    assert Photo.objects.filter(user=owner).count() == PHOTO_SLOTS
    assert Photo.objects.get(user=owner, slot=4)


def test_removing_a_photo_of_another_user_gets_404_and_keeps_it(client, owner, stranger):
    """REQ-136, P4: quitar la foto de otro da 404 y no la toca; igual con una inexistente."""
    photo = make_photo(owner)
    log_in(client, stranger)
    assert client.post(reverse(QUITAR, args=[photo.pk])).status_code == 404
    assert client.post(reverse(QUITAR, args=[999999])).status_code == 404
    assert Photo.objects.filter(pk=photo.pk).exists()


def test_removing_only_answers_post(client, owner):
    """REQ-136: quitar por GET no borra (405)."""
    photo = make_photo(owner)
    log_in(client, owner)
    assert client.get(reverse(QUITAR, args=[photo.pk])).status_code == 405
    assert Photo.objects.filter(pk=photo.pk).exists()


def test_the_remove_button_posts_with_csrf_for_each_photo(client, owner):
    """REQ-136: cada foto lleva su botón de quitar como formulario POST con CSRF."""
    made = fill(owner, 2)
    log_in(client, owner)
    html = client.get(reverse(FOTOS)).content.decode()
    for photo in made:
        assert f'action="{reverse(QUITAR, args=[photo.pk])}"' in html
    assert html.count("csrfmiddlewaretoken") >= 3  # dos de quitar, una de subir (más las del encabezado)
    strict = Client(enforce_csrf_checks=True)
    log_in(strict, owner)
    assert strict.post(reverse(QUITAR, args=[made[0].pk])).status_code == 403
    assert Photo.objects.filter(pk=made[0].pk).exists()


# --- Usuario de lectura y menú ---------------------------------------------------------------


def test_the_read_user_can_upload_and_remove_their_own_photos(client):
    """REQ-136: el usuario de lectura sube y quita sus fotos (no es una acción de decisión)."""
    reader = make_user("lector", Role.READ)
    log_in(client, reader)
    assert client.get(reverse(FOTOS)).status_code == 200
    assert post_photo(client).status_code == 302
    photo = Photo.objects.get(user=reader)
    assert client.post(reverse(QUITAR, args=[photo.pk])).status_code == 302
    assert not Photo.objects.filter(user=reader).exists()


@pytest.mark.parametrize("role", [Role.READ, Role.READ_WRITE])
def test_the_user_menu_links_to_my_photos(client, role):
    """REQ-136: el menú del usuario trae el enlace «Mis fotos» a la pantalla del perfil."""
    user = make_user("con-menu", role)
    log_in(client, user)
    html = client.get(reverse(FOTOS)).content.decode()
    menu = re.search(r'<div id="menu-usuario".*?</form>', html, re.S).group(0)
    assert f'href="{reverse(FOTOS)}"' in menu
    assert "Mis fotos" in menu
