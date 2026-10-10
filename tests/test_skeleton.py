"""Test de humo del esqueleto de Django (T-005).

Comprueba que el proyecto arranca, que WhiteNoise sirve un archivo estático y que la
integración de pgvector para Django guarda y lee un vector. No implementa un requisito
funcional: habilita la pantalla (REQ-013) y el ingreso (REQ-016).
"""

from pathlib import Path

import pytest
from django.conf import settings
from django.core.management import call_command
from django.db import connection, models
from django.test import Client, override_settings
from django.test.utils import isolate_apps
from pgvector.django import L2Distance, VectorField

STYLESHEET = "css/evaluon.css"


@pytest.mark.django_db
def test_project_starts():
    """REQ-013, REQ-016: la configuración pasa las comprobaciones de Django y la
    aplicación WSGI que usa Gunicorn se carga.

    Las comprobaciones de los campos generados leen la versión de Postgres: en serie ya la
    había leído una prueba anterior; en paralelo esta puede ser la primera del proceso
    (T-224), por eso pide la base."""
    call_command("check", fail_level="WARNING")

    from evaluon.wsgi import application

    assert callable(application)


def test_whitenoise_serves_static_file(tmp_path):
    """REQ-013: WhiteNoise sirve la hoja de estilos desde los archivos reunidos por
    collectstatic, sin servidor web aparte y con DEBUG apagado."""
    assert settings.DEBUG is False
    source = Path(settings.BASE_DIR) / "evaluon" / "static" / STYLESHEET
    assert source.is_file()

    with override_settings(STATIC_ROOT=tmp_path):
        call_command("collectstatic", interactive=False, verbosity=0)
        # Un cliente nuevo arma la cadena de middleware con STATIC_ROOT de la prueba.
        response = Client().get(settings.STATIC_URL + STYLESHEET)

    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/css")
    # WhiteNoise contesta con un archivo entero; la vista de Django no participa.
    assert response.__class__.__module__.startswith("whitenoise")
    body = b"".join(response.streaming_content)
    assert body == source.read_bytes()


@pytest.mark.django_db
@isolate_apps("tests")
def test_pgvector_stores_and_reads_vector():
    """REQ-013: la integración de pgvector para Django guarda un vector y lo lee igual,
    y ordena por distancia. El modelo existe solo dentro de esta prueba."""

    class SkeletonVector(models.Model):
        embedding = VectorField(dimensions=3)

        class Meta:
            app_label = "tests"

    # La extensión y la tabla se crean dentro de la transacción de la prueba y se
    # deshacen al terminar: no queda nada en la base de pruebas.
    with connection.cursor() as cursor:
        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
    with connection.schema_editor() as editor:
        editor.create_model(SkeletonVector)

    near = SkeletonVector.objects.create(embedding=[1.0, 2.0, 3.0])
    SkeletonVector.objects.create(embedding=[-5.0, 0.5, 9.0])

    stored = SkeletonVector.objects.get(pk=near.pk)
    assert [float(x) for x in stored.embedding] == [1.0, 2.0, 3.0]

    closest = SkeletonVector.objects.order_by(
        L2Distance("embedding", [1.0, 2.0, 3.5])
    ).first()
    assert closest.pk == near.pk
