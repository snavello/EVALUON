"""Entrega del documento original con sesión (T-036; plan 001, "Pantalla, acceso y
comandos", "Documento original"; ADR-0005).

La vista lee el archivo de `norms_document_file` y lo entrega byte por byte. Un PDF va
para abrirse en el visor del navegador; una página web guardada va con una política de
contenido que no deja ejecutar scripts ni cargar recursos de internet, sin tocar el
archivo. Los archivos de prueba son públicos (extracto del anexo de la Disposición AFIP
247/2022) o sintéticos (la página guardada, con scripts y recursos externos como los de
Infoleg) (P4).
"""

import hashlib
from pathlib import Path

import pytest
from django.shortcuts import resolve_url
from django.urls import reverse

from evaluon.norms.models import DocumentFile
from tests.conftest import TEST_PASSWORD

pytestmark = pytest.mark.django_db

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
PDF_FIXTURE = FIXTURES / "disp-247-2022-anexo-extracto.pdf"
HTML_FIXTURE = FIXTURES / "t036-pagina-guardada.htm"


def sha256(content):
    return hashlib.sha256(bytes(content)).hexdigest()


def directives(policy):
    """Política de contenido como diccionario directiva -> lista de valores."""
    parsed = {}
    for part in policy.split(";"):
        tokens = part.split()
        if tokens:
            parsed[tokens[0].lower()] = tokens[1:]
    return parsed


@pytest.fixture
def load_original(make_norm, make_document):
    """Guarda un documento con su archivo original como lo deja la carga: la huella y
    el tamaño del documento son los del archivo."""

    def _load(path, file_format, part="cuerpo"):
        content = path.read_bytes()
        document = make_document(
            make_norm(),
            part=part,
            file_name=path.name,
            file_format=file_format,
            file_size=len(content),
            file_sha256=sha256(content),
        )
        DocumentFile.objects.create(document=document, content=content)
        return document

    return _load


@pytest.fixture
def logged_client(client, read_user):
    assert client.login(username=read_user.username, password=TEST_PASSWORD)
    return client


def original_url(document):
    return reverse("norms:original", args=[document.pk])


# --- Lo entregado es el archivo cargado (REQ-002) -------------------------------------


@pytest.mark.parametrize(
    "path, file_format", [(PDF_FIXTURE, "pdf"), (HTML_FIXTURE, "html")]
)
def test_delivered_file_has_the_loaded_fingerprint(
    logged_client, load_original, path, file_format
):
    """REQ-002: la huella de lo que entrega la vista es igual a la del archivo cargado,
    en PDF y en página web guardada."""
    document = load_original(path, file_format)

    response = logged_client.get(original_url(document))

    assert response.status_code == 200
    delivered = response.content
    assert sha256(delivered) == document.file_sha256 == sha256(path.read_bytes())
    assert len(delivered) == document.file_size


def test_route_has_a_name_for_the_templates(make_norm, make_document):
    """REQ-002: la ruta lleva nombre, para que las citas (T-037) y la búsqueda (T-041)
    enlacen el original de cada parte."""
    document = make_document(make_norm())
    assert reverse("norms:original", args=[document.pk]) == (
        f"/normas/documentos/{document.pk}/original/"
    )


# --- PDF: para el visor del navegador (REQ-002) ---------------------------------------


def test_pdf_opens_in_the_browser_viewer(logged_client, load_original):
    """REQ-002: un PDF se entrega como PDF y para mostrarse en el navegador, no para
    descargarse, con el nombre con que se cargó."""
    document = load_original(PDF_FIXTURE, "pdf", part="anexo")

    response = logged_client.get(original_url(document))

    assert response["Content-Type"] == "application/pdf"
    disposition = response["Content-Disposition"]
    assert disposition.startswith("inline")
    assert PDF_FIXTURE.name in disposition
    assert response["X-Content-Type-Options"] == "nosniff"


# --- Página web guardada: aislada por la cabecera (REQ-002) ---------------------------


def test_saved_web_page_is_isolated_by_the_policy(logged_client, load_original):
    """REQ-002: una página web guardada se entrega con una política de contenido que
    impide ejecutar scripts y cargar recursos de internet."""
    document = load_original(HTML_FIXTURE, "html")

    response = logged_client.get(original_url(document))

    policy = directives(response["Content-Security-Policy"])
    # `sandbox` sin permisos: sin scripts, sin formularios, sin ventanas nuevas y con
    # un origen propio, sin acceso a la sesión.
    assert policy["sandbox"] == []
    # Nada se carga de ningún lado salvo el estilo escrito dentro de la página.
    assert policy["default-src"] == ["'none'"]
    assert "script-src" not in policy
    assert all(
        "http" not in value and "'self'" not in value and "*" not in value
        for values in policy.values()
        for value in values
    )
    assert response["X-Content-Type-Options"] == "nosniff"


def test_saved_web_page_is_not_modified(logged_client, load_original):
    """REQ-002: la restricción va en la cabecera; el archivo sale tal cual, con sus
    scripts y su codificación, y el navegador lee la codificación que declara la
    página."""
    original = HTML_FIXTURE.read_bytes()
    assert b"<script" in original and b"https://" in original
    document = load_original(HTML_FIXTURE, "html")

    response = logged_client.get(original_url(document))

    assert response.content == original
    assert response["Content-Type"] == "text/html"
    assert response["Content-Disposition"].startswith("inline")


def test_pdf_keeps_the_site_policy(logged_client, load_original):
    """REQ-002: el aislamiento es solo para la página web guardada; el PDF lleva la
    política general del sitio, sin `sandbox`."""
    document = load_original(PDF_FIXTURE, "pdf")

    response = logged_client.get(original_url(document))

    policy = directives(response["Content-Security-Policy"])
    assert "sandbox" not in policy
    assert policy["default-src"] == ["'self'"]


# --- Sesión y documento inexistente (REQ-002) -----------------------------------------


@pytest.mark.parametrize(
    "path, file_format", [(PDF_FIXTURE, "pdf"), (HTML_FIXTURE, "html")]
)
def test_without_session_redirects_to_login(client, load_original, path, file_format):
    """REQ-002: el original es solo para quien ingresó; sin sesión se redirige al
    ingreso y no se entrega el archivo."""
    document = load_original(path, file_format)
    url = original_url(document)

    response = client.get(url)

    assert response.status_code == 302
    assert response["Location"].startswith(resolve_url("accounts:login"))
    assert path.read_bytes() not in response.content


def test_unknown_document_is_not_found(logged_client):
    """REQ-002: un documento que no existe da "no encontrado"."""
    response = logged_client.get(reverse("norms:original", args=[999999]))
    assert response.status_code == 404


def test_document_without_file_is_not_found(logged_client, make_norm, make_document):
    """REQ-002: un documento sin archivo guardado da "no encontrado", no un error."""
    document = make_document(make_norm())
    response = logged_client.get(original_url(document))
    assert response.status_code == 404


def test_only_get_is_accepted(logged_client, load_original):
    """REQ-002: la vista solo entrega; no acepta envíos."""
    document = load_original(PDF_FIXTURE, "pdf")
    response = logged_client.post(original_url(document))
    assert response.status_code == 405
