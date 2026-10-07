#!/usr/bin/env bash
# Instancia de demostración (specs/013-recorrido-procedimiento/demo.md).
#   scripts/demo.sh subir      levanta la demostración (base propia) en 127.0.0.1:DEMO_PORT
#   scripts/demo.sh usuarios   crea un evaluador y un operador con claves generadas
#   scripts/demo.sh bajar      detiene los contenedores; conserva la base de la demostración
#   scripts/demo.sh borrar     baja y BORRA la base y los volúmenes de la demostración
#   scripts/demo.sh estado     muestra contenedores y comprobaciones
# Los secretos viven fuera del repositorio. Requiere la pila `evaluon` (modelos) levantada.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."
COORD="${DEMO_DIR:-/c/Users/snave/Documents/dev/evaluon-local/coord}"
ENV_FILE="${DEMO_ENV_FILE:-$COORD/demo.env}"
USERS_FILE="${DEMO_USERS_FILE:-$COORD/demo-usuarios.txt}"
dc() { docker compose -f docker-compose.demo.yml --env-file "$(cygpath -m "$ENV_FILE" 2>/dev/null || echo "$ENV_FILE")" "$@"; }

crear_env() {
    if [ ! -f "$ENV_FILE" ]; then
        mkdir -p "$(dirname "$ENV_FILE")"
        ( umask 077
          { echo "POSTGRES_PASSWORD=$(openssl rand -hex 24)"
            echo "DJANGO_SECRET_KEY=$(openssl rand -hex 40)"
            echo "DEMO_PORT=8001"; } > "$ENV_FILE" )
        echo "demo: se generó $ENV_FILE (fuera del repositorio)."
    fi
}

alta() {  # alta USUARIO ROL_COMISION CLAVE
    dc run --rm --no-deps -e "DEMO_PW=$3" demo_app python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'evaluon.settings')
django.setup()
from django.core.management import call_command
from evaluon.accounts import permissions
permissions.read_password = lambda prompt: os.environ['DEMO_PW']
call_command('crear_usuario', '$1', rol='lectura-escritura', rol_comision='$2')
"
}

case "${1:-}" in
    subir)
        crear_env
        docker network inspect evaluon_internal >/dev/null 2>&1 || {
            echo "demo: falta la red evaluon_internal; levantar antes la pila de modelos (docker compose up -d)." >&2; exit 1; }
        dc up -d
        ;;
    usuarios)
        crear_env
        if [ -f "$USERS_FILE" ]; then echo "demo: ya existe $USERS_FILE; no se crean de nuevo." >&2; exit 1; fi
        pw_e="$(openssl rand -base64 18 | tr -d '/+=' )Aa1"
        pw_o="$(openssl rand -base64 18 | tr -d '/+=' )Aa1"
        alta demo_evaluador evaluador "$pw_e"
        alta demo_operador operador "$pw_o"
        ( umask 077
          { echo "Instancia de demostración de EVALUON (http://127.0.0.1:${DEMO_PORT:-8001}/)"
            echo "demo_evaluador  $pw_e   (evaluador; incluye operador)"
            echo "demo_operador   $pw_o   (operador)"; } > "$USERS_FILE" )
        echo "demo: usuarios creados; claves en $USERS_FILE"
        ;;
    bajar)
        dc down
        ;;
    borrar)
        dc down -v --remove-orphans
        rm -f "$USERS_FILE" "$ENV_FILE"
        echo "demo: contenedores, redes propias, volúmenes y archivos de secretos borrados."
        ;;
    estado)
        dc ps -a
        ;;
    *)
        sed -n '2,9p' "$0"; exit 2
        ;;
esac
