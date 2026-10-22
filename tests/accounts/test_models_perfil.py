"""Perfil del usuario: tema y fotos personales (T-308; REQ-134, REQ-136, REQ-138;
ADR-0073 y ADR-0074).

El tema (`User.theme`) es `claro` o `negro` y vale en cualquier equipo porque se guarda en el
usuario. Las fotos (`Photo`, tabla `accounts_photo`) se guardan en la base, hasta 10 por usuario
y 2 MiB cada una; las restricciones las hace valer la base. `photos.pick_for` devuelve por ahora
solo la foto de la casa.

Los usuarios son sintéticos y las imágenes son bytes sueltos: ninguna foto sale de un archivo
del repositorio (P4).
"""

import hashlib

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, connection, transaction
from django.test import RequestFactory

from evaluon.accounts import photos
from evaluon.accounts.models import Photo, Role
from tests.conftest import TEST_PASSWORD

MAX_SIZE = 2 * 1024 * 1024


def make_user(username="con-perfil", **extra):
    return get_user_model().objects.create_user(
        username=username, password=TEST_PASSWORD, role=Role.READ, **extra
    )


def make_photo(user, slot=0, content=b"bytes-de-prueba", **extra):
    values = dict(
        user=user,
        slot=slot,
        content=content,
        sha256=hashlib.sha256(content).hexdigest(),
        width=10,
        height=10,
        size=len(content),
    )
    values.update(extra)
    return Photo.objects.create(**values)


# --- Tema ------------------------------------------------------------------------------


@pytest.mark.django_db
def test_theme_is_claro_by_default():
    """REQ-134: el tema de inicio de un usuario es gris y blanco (`claro`)."""
    user = make_user()
    user.refresh_from_db()
    assert user.theme == "claro"


@pytest.mark.django_db
def test_theme_negro_is_saved_in_the_user():
    """REQ-134: la elección queda guardada en el usuario: otro equipo la lee de la base."""
    user = make_user()
    user.theme = "negro"
    user.save(update_fields=["theme"])
    assert get_user_model().objects.get(pk=user.pk).theme == "negro"


@pytest.mark.django_db
def test_database_rejects_an_unknown_theme():
    """REQ-134: la base no acepta un tema fuera de `claro` y `negro` (ADR-0074)."""
    with pytest.raises(IntegrityError), transaction.atomic():
        make_user("tema-raro", theme="otro")


# --- Fotos: restricciones de la base -------------------------------------------------------


@pytest.mark.django_db
def test_a_photo_is_saved_with_its_data_and_its_date():
    """REQ-136: la foto guarda contenido, huella, medidas y tamaño, con su fecha de alta."""
    user = make_user()
    photo = make_photo(user, slot=3, content=b"abc")
    photo.refresh_from_db()
    assert bytes(photo.content) == b"abc"
    assert photo.sha256 == hashlib.sha256(b"abc").hexdigest()
    assert (photo.slot, photo.width, photo.height, photo.size) == (3, 10, 10, 3)
    assert photo.created_at is not None


@pytest.mark.django_db
@pytest.mark.parametrize("slot", [0, 9])
def test_slots_zero_and_nine_are_accepted(slot):
    """REQ-136: las ranuras válidas van de 0 a 9 (hasta 10 fotos)."""
    make_photo(make_user(), slot=slot)


@pytest.mark.django_db
@pytest.mark.parametrize("slot", [-1, 10])
def test_database_rejects_a_slot_out_of_range(slot):
    """REQ-136: la base rechaza la ranura -1 y la 10, así que no hay una 11.ª foto."""
    user = make_user()
    with pytest.raises(IntegrityError), transaction.atomic():
        make_photo(user, slot=slot)


@pytest.mark.django_db
def test_database_rejects_two_photos_of_one_user_in_the_same_slot():
    """REQ-136: la ranura es única por usuario; vale aun con dos subidas a la vez."""
    user = make_user()
    make_photo(user, slot=2)
    with pytest.raises(IntegrityError), transaction.atomic():
        make_photo(user, slot=2, content=b"otra")


@pytest.mark.django_db
def test_two_users_can_use_the_same_slot():
    """REQ-136: la unicidad es por usuario: cada uno tiene sus diez ranuras."""
    make_photo(make_user("uno"), slot=0)
    make_photo(make_user("dos"), slot=0)
    assert Photo.objects.count() == 2


@pytest.mark.django_db
def test_database_accepts_2_mib_and_rejects_one_byte_more():
    """REQ-136: el tope es de 2 MiB (2.097.152 bytes), lo hace valer la base."""
    user = make_user()
    make_photo(user, slot=0, size=MAX_SIZE)
    with pytest.raises(IntegrityError), transaction.atomic():
        make_photo(user, slot=1, size=MAX_SIZE + 1)


@pytest.mark.django_db
def test_deleting_the_user_deletes_its_photos():
    """REQ-136: las fotos son del usuario; si se lo da de baja se van con él (CASCADE)."""
    user = make_user("se-va")
    other = make_user("se-queda")
    make_photo(user, slot=0)
    make_photo(user, slot=1)
    make_photo(other, slot=0)
    user.delete()
    assert list(Photo.objects.values_list("user__username", flat=True)) == ["se-queda"]


def test_the_table_is_accounts_photo():
    """REQ-136: la tabla se llama `accounts_photo` (ADR-0073)."""
    assert Photo._meta.db_table == "accounts_photo"


# --- Migración reversible ------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_the_migration_is_reversible_over_existing_users():
    """REQ-134, REQ-136: con usuarios ya guardados, la 0003 se revierte y se vuelve a aplicar;
    los usuarios existentes quedan en `claro` y sin fotos."""
    from django.db.migrations.executor import MigrationExecutor

    user = make_user("anterior")
    previous = [("accounts", "0002_commission_role")]
    latest = [
        ("accounts", MigrationExecutor(connection).loader.graph.leaf_nodes("accounts")[0][1])
    ]
    assert latest[0][1] == "0003_tema_y_fotos"
    try:
        MigrationExecutor(connection).migrate(previous)
        with connection.cursor() as cursor:
            cursor.execute("SELECT to_regclass('accounts_photo')")
            assert cursor.fetchone() == (None,)
            cursor.execute(
                "SELECT count(*) FROM information_schema.columns "
                "WHERE table_name = 'accounts_user' AND column_name = 'theme'"
            )
            assert cursor.fetchone() == (0,)
            cursor.execute("SELECT count(*) FROM accounts_user WHERE id = %s", [user.pk])
            assert cursor.fetchone() == (1,)
        MigrationExecutor(connection).migrate(latest)
        migrated = get_user_model().objects.get(pk=user.pk)
        assert migrated.theme == "claro"
        assert Photo.objects.count() == 0
    finally:
        MigrationExecutor(connection).migrate(latest)


# --- La foto de la casa ---------------------------------------------------------------------


def test_pick_for_returns_the_house_photo():
    """REQ-136, REQ-138: sin fotos propias se muestra la foto de la casa, con su rótulo."""
    request = RequestFactory().get("/")
    picked = photos.pick_for(request)
    assert picked.photo_id is None
    assert picked.label == "Foto de la casa"
    assert picked.url.endswith("diseno/casa/biblioratos-bn.jpg")


def test_the_house_photo_and_its_credit_are_in_the_static_files():
    """REQ-136: la foto de la casa está en los estáticos, con su crédito al lado."""
    from django.contrib.staticfiles import finders

    assert finders.find("diseno/casa/biblioratos-bn.jpg")
    credit = finders.find("diseno/casa/CREDITOS.txt")
    assert credit
    with open(credit, encoding="utf-8") as handle:
        assert "Unsplash" in handle.read()


def test_the_reference_histogram_is_computed_once():
    """REQ-136: el histograma de referencia (el de la foto de la casa) se calcula una sola
    vez y se guarda en memoria para T-319."""
    photos.reference_histogram.cache_clear()
    first = photos.reference_histogram()
    second = photos.reference_histogram()
    assert first is second
    assert photos.reference_histogram.cache_info().misses == 1
    assert len(first) == 256
    assert sum(first) > 0
