#!/usr/bin/env bash
# Lo que ejecuta el servicio `migrate` antes de que arranque `app` (plan 001, "Migraciones
# y respaldo"; ADR-0005).
#
# - Base vacía: aplica las migraciones. No hay nada que respaldar, y un equipo limpio llega
#   al sistema funcionando con una sola orden (P5).
# - Base con datos: no migra. Solo comprueba con `migrate --check`; si hay migraciones
#   pendientes termina con error, muestra el procedimiento y `app` no arranca.
#
# "Vacía" quiere decir: ninguna tabla fuera de los esquemas del sistema, salvo la tabla de
# control de Django (django_migrations) sin ninguna migración aplicada.

set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

state="$(python - <<'PY'
import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "evaluon.settings")
django.setup()

from django.db import connection

with connection.cursor() as cursor:
    cursor.execute(
        "SELECT schemaname, tablename FROM pg_tables"
        " WHERE schemaname NOT IN ('pg_catalog', 'information_schema')"
    )
    tables = cursor.fetchall()
    applied = 0
    if ("public", "django_migrations") in tables:
        cursor.execute("SELECT count(*) FROM django_migrations")
        applied = cursor.fetchone()[0]

others = [t for t in tables if t != ("public", "django_migrations")]
print("empty" if not others and applied == 0 else "data")
PY
)"

if [ "$state" = "empty" ]; then
    echo "migrate: la base está vacía; se aplican las migraciones."
    exec python manage.py migrate --noinput
fi

echo "migrate: la base tiene datos; solo se comprueba que no haya migraciones pendientes."
if python manage.py migrate --check; then
    echo "migrate: no hay migraciones pendientes."
    exit 0
fi

cat >&2 <<'MSG'
migrate: hay migraciones pendientes y la base tiene datos. No se migra sin respaldo previo,
y la aplicación no arranca. Procedimiento:
  1. Detener app:   docker compose stop app
  2. Respaldar:     docker compose exec -T db sh -c 'pg_dump -Fc -U "$POSTGRES_USER" "$POSTGRES_DB"' > backups/evaluon-AAAA-MM-DD.dump
  3. Aplicar:       docker compose run --rm --no-deps app python manage.py migrate
  4. Levantar todo: docker compose up -d
MSG
exit 1
