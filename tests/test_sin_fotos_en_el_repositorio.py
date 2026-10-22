"""Las fotos no entran al repositorio (T-308; REQ-136; ADR-0073; P4).

Las fotos personales viven en la base (volumen `pgdata`) y los respaldos van a `backups/` o a una
carpeta fuera del repositorio. Este test falla si aparece un archivo de imagen fuera de los
lugares permitidos, o si el `.gitignore` deja de cubrir `backups/`, `pgdata/` y `*.dump`.

Permitidos: la foto de la casa (`evaluon/static/diseno/casa/`), la marca
(`evaluon/static/marca/`), la carpeta de diseño ya versionada (`docs/`) y los dos PNG
sintéticos que `tests/assessment/data/vision/generar.py` dibuja con código para los tests de
lectura con visión (T-160); ninguno es una foto de una persona.

Si el repositorio está disponible (`git ls-files`) se miran los archivos versionados; si no (la
imagen de pruebas monta solo `evaluon/`, `tests/` y `scripts/`), se recorren esas tres carpetas.
"""

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tif", ".tiff", ".heic",
                  ".heif", ".avif", ".ico"}
ALLOWED_PREFIXES = (
    "evaluon/static/diseno/casa/",
    "evaluon/static/marca/",
    "docs/",
    "tests/assessment/data/vision/",
)
# Carpetas que monta la imagen de pruebas (docker-compose.yml): el resto de /app es lo que quedó de
# la construcción de la imagen y no es el repositorio.
MOUNTED_DIRS = ("evaluon", "tests", "scripts")
SKIPPED_DIRS = {"__pycache__"}


def repository_files():
    """Rutas relativas (con `/`) de los archivos del repositorio, o de lo que haya montado."""
    if (ROOT / ".git").exists():
        try:
            out = subprocess.run(
                ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True
            ).stdout.decode("utf-8")
            return [name for name in out.split("\0") if name]
        except (OSError, subprocess.CalledProcessError):
            pass
    found = []
    for folder in MOUNTED_DIRS:
        for path in (ROOT / folder).rglob("*"):
            relative = path.relative_to(ROOT)
            if SKIPPED_DIRS & set(relative.parts) or not path.is_file():
                continue
            found.append(relative.as_posix())
    return found


def stray_images(names):
    """Los archivos de imagen de `names` que están fuera de los lugares permitidos."""
    return [
        name
        for name in names
        if Path(name).suffix.lower() in IMAGE_SUFFIXES and not name.startswith(ALLOWED_PREFIXES)
    ]


def test_no_image_files_outside_the_allowed_folders():
    """REQ-136: ningún archivo de imagen fuera de la foto de la casa, la marca y `docs/`."""
    stray = stray_images(repository_files())
    assert stray == [], f"Archivos de imagen fuera de los lugares permitidos: {stray}"


def test_the_check_flags_images_in_the_wrong_places_and_lets_the_allowed_ones_pass():
    """REQ-136: prueba de alteración. Una foto en una carpeta de fotos, en `evaluon/` o en la
    raíz se detecta; las de la casa, la marca y `docs/` no."""
    names = [
        "fotos/abuela.jpg",
        "evaluon/media/fotos/1.JPEG",
        "perfil.webp",
        "evaluon/static/diseno/casa/biblioratos-bn.jpg",
        "evaluon/static/marca/isotipo.png",
        "docs/diseno/marca/maqueta-aprobada.png",
        "evaluon/models.py",
    ]
    assert stray_images(names) == ["fotos/abuela.jpg", "evaluon/media/fotos/1.JPEG", "perfil.webp"]


def test_the_repository_is_actually_scanned():
    """REQ-136: la lista de archivos no está vacía, así que el primer test mira algo."""
    names = repository_files()
    assert any(name.endswith("evaluon/accounts/models.py") for name in names)


def test_gitignore_covers_backups_data_and_dumps():
    """REQ-136: el `.gitignore` cubre `backups/`, `pgdata/` y `*.dump`."""
    gitignore = ROOT / ".gitignore"
    if not gitignore.exists():
        pytest.skip(".gitignore no está montado en este entorno: montarlo para comprobarlo")
    lines = {line.strip() for line in gitignore.read_text(encoding="utf-8").splitlines()}
    for rule in ("backups/", "pgdata/", "*.dump"):
        assert rule in lines, f"Falta {rule} en .gitignore"
