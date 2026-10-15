#!/usr/bin/env bash
# Instancia clonada de la feature 016 (specs/016-calidad-medible/entorno.md; REQ-125).
#   scripts/clon.sh subir                 levanta el clon (base, migraciones, app, worker) en 127.0.0.1:CLON_PORT (8016)
#   scripts/clon.sh restaurar [--archivo RUTA] [--forzar]
#                                         respaldo nuevo de la base de 8000 (solo lectura) y su restauración en clon_db
#   scripts/clon.sh ventana-abrir [--simular]    detiene el motor y el worker de 8000 y arranca el motor del clon
#   scripts/clon.sh ventana-cerrar [--simular]   baja el motor del clon, devuelve 8000 y lo comprueba
#   scripts/clon.sh bajar                 detiene los contenedores del clon; conserva su base
#   scripts/clon.sh estado                muestra contenedores, motores, ventana, cola y comprobaciones (solo lectura)
#   scripts/clon.sh ejecutar ORDEN...     corre una orden en un contenedor nuevo del clon (por ejemplo, manage.py medir_...)
# --simular (o DRY_RUN=1): imprime lo que haría, comprueba las condiciones y no cambia nada.
# Variables: COORD_DIR (carpeta local del Coordinador, fuera del repositorio; trae clon.env) o
# CLON_ENV_FILE; CLON_CODE_DIR (código que se monta; solo al crear clon.env o para cambiarlo en
# una corrida). Los secretos viven en clon.env, nunca en el repositorio.
set -euo pipefail

# Git Bash convierte los argumentos que parecen rutas de Linux (/models, /app) al pasarlos a docker.
export MSYS_NO_PATHCONV=1

cd "$(dirname "${BASH_SOURCE[0]}")/.."
COMPOSE_FILE_CLON=docker-compose.clon.yml
PROJECT=evaluon-016
P8000="${CLON_PROYECTO_8000:-evaluon}"          # proyecto de Compose de la instancia de trabajo
URL8000="${CLON_URL_8000:-http://127.0.0.1:8000}"
GPU_MAX_MIB="${CLON_GPU_MAX_MIB:-6000}"        # memoria de video usada tolerada con el motor de 8000 detenido
ESPERA_MOTOR="${CLON_ESPERA_MOTOR:-1500}"      # segundos máximos de espera de la carga de un motor
CLON_ALIAS="qwen3.8-27b-ud-q4_k_m"
MODELO_ARCHIVOS=(Qwen3.8-27B-UD-Q4_K_M.gguf mmproj-Qwen3.8-27B-F16.gguf)

SIMULAR=0
[ "${DRY_RUN:-0}" = "1" ] && SIMULAR=1

mpath() { cygpath -m "$1" 2>/dev/null || echo "$1"; }
falla() { echo "clon: $*" >&2; exit 1; }

if [ -n "${CLON_ENV_FILE:-}" ]; then
    ENV_FILE="$CLON_ENV_FILE"
elif [ -n "${COORD_DIR:-}" ]; then
    ENV_FILE="$COORD_DIR/clon.env"
else
    falla "falta COORD_DIR (carpeta local del Coordinador, fuera del repositorio) o CLON_ENV_FILE."
fi
RESPALDOS_DIR="${CLON_RESPALDOS_DIR:-$(dirname "$ENV_FILE")/respaldos-clon}"
MARCA_RESTAURADO="$(dirname "$ENV_FILE")/clon-restaurado.txt"

dc()    { docker compose -p "$PROJECT" -f "$COMPOSE_FILE_CLON" --env-file "$(mpath "$ENV_FILE")" "$@"; }
dcall() { dc --profile '*' "$@"; }   # incluye el perfil `motor` (para detener, bajar y listar)

var_env() {  # var_env NOMBRE: el valor del entorno o, si no está, el de clon.env
    local v="${!1:-}"
    if [ -z "$v" ] && [ -f "$ENV_FILE" ]; then v="$(grep -E "^$1=" "$ENV_FILE" | tail -1 | cut -d= -f2- || true)"; fi
    printf '%s' "$v"
}

asegurar_var() {  # asegurar_var NOMBRE VALOR: la agrega a clon.env si falta
    grep -qE "^$1=" "$ENV_FILE" || echo "$1=$2" >> "$ENV_FILE"
}

crear_env() {
    if [ ! -f "$ENV_FILE" ]; then
        local code="${CLON_CODE_DIR:-}"
        [ -n "$code" ] || falla "falta CLON_CODE_DIR (copia de trabajo de 016-integracion) para crear $ENV_FILE."
        mkdir -p "$(dirname "$ENV_FILE")"
        ( umask 077
          { echo "POSTGRES_PASSWORD=$(openssl rand -hex 24)"
            echo "DJANGO_SECRET_KEY=$(openssl rand -hex 40)"
            echo "CLON_PORT=8016"; } > "$ENV_FILE" )
        echo "clon: se generó $ENV_FILE (fuera del repositorio)."
    fi
    local code="${CLON_CODE_DIR:-}"
    [ -z "$code" ] || asegurar_var CLON_CODE_DIR "$(mpath "$code")"
    if [ -z "$(var_env CLON_MODELS_DIR)" ]; then
        # `models/` vive en la carpeta raíz del repositorio (ignorada por git); se llega a ella
        # desde cualquier copia de trabajo por el directorio común de git.
        local raiz
        raiz="$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")" || falla "defina CLON_MODELS_DIR."
        asegurar_var CLON_MODELS_DIR "$(mpath "$raiz/models")"
    fi
    [ -n "$(var_env CLON_CASOS_DIR)" ] || asegurar_var CLON_CASOS_DIR "$(mpath "$(dirname "$ENV_FILE")/clon-casos")"
    [ -n "$(var_env CLON_CODE_DIR)" ] || falla "falta CLON_CODE_DIR en $ENV_FILE o en el entorno."
    # La variable del entorno manda sobre clon.env; la dejamos normalizada para Compose.
    [ -z "${CLON_CODE_DIR:-}" ] || export CLON_CODE_DIR="$(mpath "$CLON_CODE_DIR")"
}

puerto_clon() { local p; p="$(var_env CLON_PORT)"; echo "${p:-8016}"; }
http_code() { curl -s -o /dev/null -m 10 -w '%{http_code}' "$1" 2>/dev/null || true; }

# --- instancia de 8000 (solo lectura, salvo en la ventana) -----------------------------

cid8000() {  # cid8000 SERVICIO [-a]: id del contenedor del servicio en el proyecto de 8000
    docker ps ${2:+$2} -q --filter "label=com.docker.compose.project=$P8000" \
        --filter "label=com.docker.compose.service=$1" --filter "label=com.docker.compose.oneoff=False" | head -1
}
corre() { [ "$(docker inspect -f '{{.State.Running}}' "$1" 2>/dev/null || echo false)" = "true" ]; }
salud() { docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}sin-chequeo{{end}}' "$1" 2>/dev/null || echo "no-existe"; }
sql8000() {  # sql8000 CONSULTA: solo SELECT sobre la base de 8000
    docker exec -i "$(cid8000 db)" sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At' <<< "$1"
}
COLA_SQL="SELECT count(*) FROM tenders_job WHERE status IN ('queued','running') AND kind NOT IN ('portal_explore','portal_review');"
cola8000() { sql8000 "$COLA_SQL" | tr -d '\r'; }
colaclon() { dc exec -T clon_db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At' <<< "$COLA_SQL" | tr -d '\r'; }
gpu_usada() { nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>/dev/null | head -1 | tr -d ' \r' || true; }
props() {  # props CONTENEDOR: alias y contexto del motor, "alias n_ctx"
    local j; j="$(docker exec "$1" curl -s -m 10 localhost:8080/props 2>/dev/null || true)"
    printf '%s %s' "$(grep -o '"model_alias":"[^"]*"' <<< "$j" | head -1 | cut -d'"' -f4)" \
                   "$(grep -o '"n_ctx":[0-9]*' <<< "$j" | head -1 | cut -d: -f2)"
}
health() { docker exec "$1" curl -s -m 10 localhost:8080/health 2>/dev/null || true; }

esperar_sano() {  # esperar_sano CONTENEDOR: hasta que el chequeo de salud diga healthy
    local c="$1" t=0
    while [ "$t" -lt "$ESPERA_MOTOR" ]; do
        [ "$(salud "$c")" = "healthy" ] && return 0
        corre "$c" || { echo "clon: el contenedor $c se detuvo mientras se esperaba." >&2; return 1; }
        sleep 10; t=$((t + 10))
    done
    echo "clon: $c no quedó sano en ${ESPERA_MOTOR}s." >&2; return 1
}

describir() {
    case "$1" in
        dc)    shift; echo "docker compose -p $PROJECT -f $COMPOSE_FILE_CLON $*" ;;
        dcall) shift; echo "docker compose -p $PROJECT -f $COMPOSE_FILE_CLON --profile '*' $*" ;;
        *)     echo "$*" ;;
    esac
}
accion() {  # en --simular solo dice qué haría
    if [ "$SIMULAR" = 1 ]; then echo "[simular] haría: $(describir "$@")"; else echo "+ $(describir "$@")"; "$@"; fi
}
nombre() { docker inspect -f '{{.Name}}' "$1" 2>/dev/null | sed 's#^/##'; }

motor_clon_corre() { local id; id="$(dcall ps -q clon_generation_batch 2>/dev/null | head -1 || true)"; [ -n "$id" ] && corre "$id"; }

# --- subcomandos -------------------------------------------------------------------

cmd_subir() {
    crear_env
    docker network inspect evaluon_internal >/dev/null 2>&1 || falla "falta la red evaluon_internal; levantar antes la pila de modelos."
    docker image inspect evaluon-app:local >/dev/null 2>&1 || falla "falta la imagen evaluon-app:local (la construye la pila real)."
    local code models casos
    code="$(var_env CLON_CODE_DIR)"; models="$(var_env CLON_MODELS_DIR)"; casos="$(var_env CLON_CASOS_DIR)"
    [ -f "$code/manage.py" ] || falla "CLON_CODE_DIR ($code) no tiene manage.py: no es una copia del código."
    [ -d "$models" ] || falla "CLON_MODELS_DIR ($models) no existe."
    mkdir -p "$casos"
    dc up -d
    local t=0
    until [ "$(http_code "http://127.0.0.1:$(puerto_clon)/ingresar/")" = "200" ]; do
        t=$((t + 5)); [ "$t" -le 120 ] || { dc ps -a; falla "clon_app no responde /ingresar/ 200 en el puerto $(puerto_clon)."; }
        sleep 5
    done
    echo "clon: /ingresar/ 200 en 127.0.0.1:$(puerto_clon)."
    if [ ! -f "$MARCA_RESTAURADO" ]; then
        echo "clon: la base está recién migrada y vacía; correr 'scripts/clon.sh restaurar' para cargarle el respaldo de 8000."
    fi
}

respaldar_8000() {  # respaldar_8000 ARCHIVO: pg_dump -Fc de la base de 8000 (solo lectura)
    local out="$1" db
    db="$(cid8000 db)"
    [ -n "$db" ] || falla "no hay contenedor 'db' del proyecto $P8000 en marcha."
    mkdir -p "$(dirname "$out")"
    local cola; cola="$(cola8000 || echo '?')"
    [ "$cola" = "0" ] || echo "clon: aviso: la cola de 8000 tiene $cola pedido(s) en espera o en curso; el respaldo los incluye."
    docker exec -i "$db" sh -c 'pg_dump -Fc -U "$POSTGRES_USER" "$POSTGRES_DB"' > "$out"
    [ -s "$out" ] || { rm -f "$out"; falla "el respaldo salió vacío."; }
    echo "clon: respaldo de 8000: $out ($(wc -c < "$out" | tr -d ' ') bytes)."
}

conteos_base() {  # "tabla filas" de la base del clon, una por línea y ordenadas
    dc exec -T clon_db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -F" "' <<'SQL' | tr -d '\r' | LC_ALL=C sort
SELECT format('%I.%I', schemaname, tablename),
       (xpath('/row/c/text()', query_to_xml(format('select count(*) as c from %I.%I', schemaname, tablename), false, true, '')))[1]::text
FROM pg_tables WHERE schemaname NOT IN ('pg_catalog', 'information_schema');
SQL
}

conteos_respaldo() {  # "tabla filas" de lo que trae el respaldo (los COPY de sus datos), ordenadas
    dc exec -T clon_db pg_restore --data-only -f - < "$1" | tr -d '\r' | awk '
        /^COPY / { t = $2; n = 0; dentro = 1; next }
        dentro && /^\\\.$/ { print t, n; dentro = 0; next }
        dentro { n++ }' | LC_ALL=C sort
}

cmd_restaurar() {
    local archivo="" forzar=0
    while [ $# -gt 0 ]; do
        case "$1" in
            --archivo) archivo="${2:?--archivo necesita una ruta}"; shift 2 ;;
            --forzar) forzar=1; shift ;;
            *) falla "opción desconocida: $1" ;;
        esac
    done
    crear_env
    if [ -f "$MARCA_RESTAURADO" ] && [ "$forzar" = 0 ]; then
        echo "clon: la base del clon ya fue restaurada ($(head -1 "$MARCA_RESTAURADO")) y puede tener datos propios." >&2
        falla "no se la pisa sin --forzar."
    fi
    dc up -d clon_db
    esperar_sano "$(dc ps -q clon_db | head -1)"
    if [ -z "$archivo" ]; then
        archivo="$RESPALDOS_DIR/evaluon-$(date +%Y%m%d-%H%M)-clon-016.dump"
        respaldar_8000 "$archivo"
    fi
    [ -s "$archivo" ] || falla "no existe o está vacío: $archivo"
    local entradas; entradas="$(dc exec -T clon_db pg_restore -l < "$archivo" | grep -vc '^;' || true)"
    echo "clon: el respaldo tiene $entradas entradas (pg_restore -l)."
    [ "${entradas:-0}" -gt 0 ] || falla "pg_restore -l no lee el respaldo."

    echo "clon: se detienen clon_app y clon_worker y se recrea la base del clon."
    dcall stop clon_app clon_worker >/dev/null 2>&1 || true
    local psql_admin='psql -U "$POSTGRES_USER" -d postgres -v ON_ERROR_STOP=1'
    dc exec -T clon_db sh -c "$psql_admin -c 'DROP DATABASE IF EXISTS evaluon_clon WITH (FORCE)' -c 'CREATE DATABASE evaluon_clon'" >/dev/null
    local errores; errores="$(mktemp)"
    dc exec -T clon_db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-privileges' < "$archivo" 2> "$errores" || true
    if [ -s "$errores" ]; then echo "clon: pg_restore informó:"; head -20 "$errores"; fi
    rm -f "$errores"

    echo "clon: se comparan los conteos de tablas del clon contra los del respaldo."
    local dif
    dif="$(diff <(conteos_respaldo "$archivo") <(conteos_base) || true)"
    if [ -n "$dif" ]; then echo "$dif"; falla "los conteos del clon no coinciden con los del respaldo."; fi
    local tablas filas
    tablas="$(conteos_base | wc -l | tr -d ' ')"; filas="$(conteos_base | awk '{s += $2} END {print s + 0}')"
    echo "clon: conteos iguales en $tablas tablas ($filas filas)."

    echo "clon: se aplican las migraciones pendientes sobre la copia (la base de 8000 no se escribe)."
    dc run --rm --no-deps clon_app python manage.py migrate --noinput | tail -5
    { echo "$(basename "$archivo") restaurado el $(date '+%Y-%m-%d %H:%M')"
      echo "tablas $tablas filas $filas"; } > "$MARCA_RESTAURADO"

    dc up -d clon_app
    local cola; cola="$(colaclon)"
    if [ "$cola" = "0" ]; then
        dc up -d clon_worker
    else
        echo "clon: aviso: la copia trae $cola pedido(s) en espera o en curso de 8000; clon_worker NO se arranca."
    fi
    local t=0
    until [ "$(http_code "http://127.0.0.1:$(puerto_clon)/ingresar/")" = "200" ]; do
        t=$((t + 5)); [ "$t" -le 120 ] || falla "clon_app no responde /ingresar/ 200 tras restaurar."
        sleep 5
    done
    echo "clon: restaurado; /ingresar/ 200 en 127.0.0.1:$(puerto_clon)."
}

reabrir_8000() {  # devuelve el motor y el worker de 8000 y los comprueba (la vuelta atrás de la ventana)
    local gb wk
    gb="$(cid8000 generation_batch -a)"; wk="$(cid8000 worker -a)"
    [ -n "$gb" ] && [ -n "$wk" ] || falla "no se encuentran generation_batch o worker del proyecto $P8000."
    if corre "$gb"; then echo "  8000: el motor ya está en marcha (nada que devolver)."; else accion docker start "$(nombre "$gb")"; fi
    if [ "$SIMULAR" = 0 ]; then esperar_sano "$gb"; fi
    if corre "$wk"; then echo "  8000: el worker ya está en marcha (nada que devolver)."; else accion docker start "$(nombre "$wk")"; fi
}

comprobar_8000() {  # las comprobaciones de que 8000 quedó sano; devuelve el número de fallas
    local gb wk app fallas=0 esp_alias esp_ctx got_alias got_ctx
    gb="$(cid8000 generation_batch -a)"; wk="$(cid8000 worker -a)"; app="$(cid8000 app -a)"
    esp_alias="$(docker exec "$app" printenv GENERATION_BATCH_MODEL_ALIAS 2>/dev/null | tr -d '\r' || true)"
    esp_ctx="$(docker exec "$app" printenv GENERATION_BATCH_CTX_SIZE 2>/dev/null | tr -d '\r' || true)"
    ok()  { echo "  OK     $*"; }
    mal() { echo "  FALLA  $*"; fallas=$((fallas + 1)); }
    echo "Comprobaciones de 8000:"
    if corre "$gb" && [ "$(salud "$gb")" = "healthy" ]; then ok "generation_batch en marcha y sano"; else mal "generation_batch: $(salud "$gb")"; fi
    if [ "$(health "$gb")" = '{"status":"ok"}' ]; then ok "/health del motor: ok"; else mal "/health del motor: '$(health "$gb")'"; fi
    read -r got_alias got_ctx <<< "$(props "$gb")"
    if [ -n "$esp_alias" ] && [ "$got_alias" = "$esp_alias" ] && [ "$got_ctx" = "$esp_ctx" ]; then
        ok "/props del motor: $got_alias, n_ctx $got_ctx (los que registra la aplicación)"
    else mal "/props del motor: '$got_alias' n_ctx '$got_ctx'; esperado '$esp_alias' n_ctx '$esp_ctx'"; fi
    if corre "$wk"; then ok "worker en marcha"; else mal "worker detenido"; fi
    if [ "$(salud "$app")" = "healthy" ]; then ok "app sana"; else mal "app: $(salud "$app")"; fi
    local cola; cola="$(cola8000 || echo '?')"
    if [ "$cola" = "0" ]; then ok "cola vacía"; else mal "cola con $cola pedido(s) en espera o en curso"; fi
    local c; c="$(http_code "$URL8000/ingresar/")"
    if [ "$c" = "200" ]; then ok "/ingresar/ 200 en $URL8000"; else mal "/ingresar/ respondió '$c' en $URL8000"; fi
    COMPROBAR_FALLAS=$fallas
}

# Mientras 8000 está detenido por una ventana a medio abrir, cualquier salida inesperada lo devuelve.
DETENIDO8000=0
retroceder() {  # la vuelta atrás de una ventana que no se pudo abrir
    DETENIDO8000=0
    echo "clon: se baja el motor del clon (si arrancó) y se devuelve 8000 a como estaba." >&2
    dcall rm -sf clon_generation_batch >/dev/null 2>&1 || true
    reabrir_8000
}
salvaguarda() {
    if [ "$DETENIDO8000" = 1 ]; then
        echo "clon: la ventana quedó a medias." >&2
        set +e; retroceder
    fi
}
trap salvaguarda EXIT

cmd_ventana_abrir() {
    crear_env
    echo "== ventana-abrir$([ "$SIMULAR" = 1 ] && echo ' (simulada: no se cambia nada)')"
    local gb wk app fallas=0
    gb="$(cid8000 generation_batch -a)"; wk="$(cid8000 worker -a)"; app="$(cid8000 app -a)"
    [ -n "$gb" ] && [ -n "$wk" ] || falla "no se encuentran generation_batch o worker del proyecto $P8000."
    ok()  { echo "  OK     $*"; }
    mal() { echo "  FALLA  $*"; fallas=$((fallas + 1)); }
    echo "Condiciones:"
    if motor_clon_corre; then mal "el motor del clon ya está en marcha (¿ventana abierta?)"; else ok "el motor del clon no está en marcha"; fi
    if corre "$gb"; then ok "el motor de 8000 está en marcha (se lo detendrá)"; else mal "el motor de 8000 no está en marcha (¿ventana abierta?)"; fi
    local cola; cola="$(cola8000 || echo '?')"
    if [ "$cola" = "0" ]; then ok "la cola de 8000 está vacía"; else mal "la cola de 8000 tiene $cola pedido(s) en espera o en curso"; fi
    local otros="" id
    for id in $(docker ps -q --filter "ancestor=ghcr.io/ggml-org/llama.cpp:server-cuda-b11347"); do
        case "$id" in
            "$gb"*|"$(cid8000 embeddings)"|"$(cid8000 reranker)") ;;
            *) otros="$otros $(nombre "$id")" ;;
        esac
    done
    if [ -z "$otros" ]; then ok "ningún otro motor usa la GPU (solo embeddings y reranker de 8000)"; else mal "otros motores en marcha:$otros"; fi
    local f
    for f in "${MODELO_ARCHIVOS[@]}"; do
        if [ -f "$(var_env CLON_MODELS_DIR)/$f" ]; then ok "modelo $f"; else mal "falta el modelo $(var_env CLON_MODELS_DIR)/$f"; fi
    done
    local g; g="$(gpu_usada)"
    echo "  Info   memoria de video usada ahora: ${g:-sin dato} MiB (con el motor de 8000 todavía cargado)"
    [ "$fallas" = 0 ] || falla "no se abre la ventana: $fallas condición(es) sin cumplir."

    echo "Pasos:"
    [ "$SIMULAR" = 1 ] || DETENIDO8000=1
    accion docker stop -t 120 "$(nombre "$wk")"
    accion docker stop -t 120 "$(nombre "$gb")"
    if [ "$SIMULAR" = 0 ]; then
        sleep "${CLON_PAUSA_GPU:-10}"
        g="$(gpu_usada)"
        echo "  Info   memoria de video usada con el motor detenido: ${g:-sin dato} MiB (tope $GPU_MAX_MIB)"
        if [ -n "$g" ] && [ "$g" -gt "$GPU_MAX_MIB" ]; then
            echo "clon: la GPU sigue ocupada." >&2
            retroceder; falla "ventana no abierta."
        fi
    else
        echo "[simular] comprobaría que la memoria de video usada queda en $GPU_MAX_MIB MiB o menos"
    fi
    accion dc up -d --no-deps clon_generation_batch
    if [ "$SIMULAR" = 0 ]; then
        local ce; ce="$(dcall ps -q clon_generation_batch | head -1)"
        if ! esperar_sano "$ce"; then
            echo "clon: el motor del clon no arrancó." >&2
            retroceder; falla "ventana no abierta."
        fi
        DETENIDO8000=0
        local a n; read -r a n <<< "$(props "$ce")"
        echo "  Info   motor del clon: alias $a, n_ctx $n"
        [ "$a" = "$CLON_ALIAS" ] || { echo "clon: el alias del motor del clon es '$a', no $CLON_ALIAS." >&2; }
        echo "clon: ventana abierta. 8000 sin motor ni worker hasta 'ventana-cerrar'."
    else
        echo "[simular] esperaría a que el motor del clon quede sano (hasta ${ESPERA_MOTOR}s) y comprobaría su /props ($CLON_ALIAS)"
        echo "[simular] fin: nada cambió."
    fi
}

cmd_ventana_cerrar() {
    crear_env
    echo "== ventana-cerrar$([ "$SIMULAR" = 1 ] && echo ' (simulada: no se cambia nada)')"
    if motor_clon_corre || [ "$SIMULAR" = 1 ]; then
        accion dcall rm -sf clon_generation_batch
    fi
    reabrir_8000
    COMPROBAR_FALLAS=0
    comprobar_8000
    if [ "$SIMULAR" = 1 ]; then echo "[simular] fin: nada cambió (las comprobaciones de arriba son las reales sobre el estado actual)."; fi
    [ "$COMPROBAR_FALLAS" = 0 ] || falla "8000 no quedó sano: $COMPROBAR_FALLAS comprobación(es) fallida(s)."
    echo "clon: ventana cerrada; 8000 sano."
}

cmd_bajar() {
    crear_env
    if motor_clon_corre; then falla "el motor del clon está en marcha (ventana abierta): correr antes 'ventana-cerrar' para devolver 8000."; fi
    dcall down
    echo "clon: contenedores detenidos y quitados; la base (volumen clon_pgdata) se conserva."
}

cmd_estado() {
    if [ ! -f "$ENV_FILE" ]; then echo "clon: sin $ENV_FILE; todavía no se corrió 'subir'."; return 0; fi
    local g c
    echo "== Contenedores del clon (proyecto $PROJECT)"
    dcall ps -a --format 'table {{.Name}}\t{{.Image}}\t{{.Status}}' || true
    echo "== Volúmenes del clon"
    docker volume ls --format '{{.Name}}' | grep -E "^${PROJECT}_" || echo "(ninguno)"
    echo "== Configuración"
    echo "  clon.env: $ENV_FILE (secretos no mostrados)"
    echo "  código:   $(var_env CLON_CODE_DIR)"
    echo "  modelos:  $(var_env CLON_MODELS_DIR)"
    echo "  casos:    $(var_env CLON_CASOS_DIR)"
    if [ -f "$MARCA_RESTAURADO" ]; then echo "  base:     $(head -1 "$MARCA_RESTAURADO"); $(sed -n 2p "$MARCA_RESTAURADO")"; else echo "  base:     sin restaurar"; fi
    echo "== Comprobaciones"
    c="$(http_code "http://127.0.0.1:$(puerto_clon)/ingresar/")"; echo "  clon /ingresar/ en 127.0.0.1:$(puerto_clon): ${c:-sin respuesta}"
    c="$(http_code "$URL8000/ingresar/")"; echo "  8000 /ingresar/ en $URL8000: ${c:-sin respuesta}"
    local gb; gb="$(cid8000 generation_batch -a)"
    if [ -n "$gb" ]; then
        echo "  8000 motor: $(corre "$gb" && echo en-marcha || echo DETENIDO), salud $(salud "$gb"), /health $(health "$gb"), /props $(props "$gb")"
        echo "  8000 cola: $(cola8000 2>/dev/null || echo 'sin dato')"
    else echo "  8000: no se encuentra generation_batch del proyecto $P8000"; fi
    if motor_clon_corre; then echo "  clon motor: EN MARCHA"; else echo "  clon motor: detenido"; fi
    if motor_clon_corre || { [ -n "$gb" ] && ! corre "$gb"; }; then echo "  ventana: ABIERTA (o a medias): 'ventana-cerrar' devuelve 8000"; else echo "  ventana: cerrada"; fi
    if [ -n "$(dcall ps -q clon_db 2>/dev/null | head -1)" ]; then echo "  clon cola: $(colaclon 2>/dev/null || echo 'sin dato')"; fi
    g="$(gpu_usada)"; echo "  GPU: ${g:-sin dato} MiB usados (nvidia-smi del equipo)"
}

cmd_ejecutar() {
    crear_env
    [ $# -gt 0 ] || falla "ejecutar necesita la orden a correr (por ejemplo: python manage.py check)."
    dc run --rm --no-deps clon_worker "$@"
}

orden="${1:-}"; [ $# -eq 0 ] || shift
case "$orden" in
    ventana-abrir|ventana-cerrar)
        for a in "$@"; do
            if [ "$a" = "--simular" ]; then SIMULAR=1; else falla "opción desconocida: $a"; fi
        done ;;
esac
case "$orden" in
    subir)           cmd_subir ;;
    restaurar)       cmd_restaurar "$@" ;;
    ventana-abrir)   cmd_ventana_abrir ;;
    ventana-cerrar)  cmd_ventana_cerrar ;;
    bajar)           cmd_bajar ;;
    estado)          cmd_estado ;;
    ejecutar)        cmd_ejecutar "$@" ;;
    *)               sed -n '2,12p' "$0"; exit 2 ;;
esac
