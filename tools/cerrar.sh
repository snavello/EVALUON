#!/usr/bin/env bash
# Cierre de una tarea antes de integrar (Coordinador).
# Uso: tools/cerrar.sh FEATURE NNN "mensaje del commit de gestión" [MAIN_VERIFICADO]
#   FEATURE: carpeta de specs/, por ejemplo 001-normativa.
#   MAIN_VERIFICADO: commit de main con el que el testeador corrió la suite (ADR-0012).
#     Si se da y desde ahí no entró código a main, la suite no se repite.
# Variable de entorno obligatoria: COORD_DIR, la carpeta local del Coordinador
# (fuera del repositorio) con coord.env y tNNN.json.
# Se corre desde la copia de trabajo de la tarea. Integra origin/main, aplica estado y
# avisos de tNNN.json, regenera el tablero, corre la suite si corresponde y solo si pasa
# commitea. Sale con error ante cualquier falla: con error, no se integra (ADR-0014).
set -euo pipefail
FEATURE=$1; N=$2; MSG=$3; MV=${4:-}
: "${COORD_DIR:?falta COORD_DIR}"
TASKS=specs/$FEATURE/tasks.md
TOOLS=$(cd "$(dirname "$0")" && pwd)
if [ -n "$(git status --porcelain)" ]; then echo "ARBOL SUCIO"; git status --short; exit 1; fi
git fetch -q
git merge origin/main -m "gestión: integra main en $(git branch --show-current)" >/dev/null 2>&1 || true
for f in $(git diff --name-only --diff-filter=U); do
  case $f in
    docs/tablero.md) git checkout --theirs docs/tablero.md ;;
    "$TASKS") ;;
    *) echo "CONFLICTO INESPERADO $f"; exit 1 ;;
  esac
done
py -3 "$TOOLS/resolve_tasks.py" "$TASKS"
py -3 "$TOOLS/avisos.py" "$TASKS" "$COORD_DIR/t$N.json"
if grep -rnE '^(<<<<<<< |=======\r?$|>>>>>>> )' specs docs evaluon tests; then echo MARCAS; exit 1; fi
py -3 tools/tablero.py
git merge-base --is-ancestor origin/main HEAD || { echo "FALTA MAIN"; exit 1; }
CODE="evaluon tests docker-compose.yml pyproject.toml Dockerfile scripts manage.py"
if [ -n "$MV" ] && git diff --quiet "$MV" origin/main -- $CODE 'requirements*'; then
  echo "SUITE OMITIDA: sin cambios de código en main desde $MV (ADR-0012)"
else
  P=evaluon-t$N-cierre
  docker compose -p $P --env-file "$COORD_DIR/coord.env" up -d db >/dev/null 2>&1
  set +e
  # En paralelo (T-224, ver pyproject.toml): SUITE_WORKERS procesos, 8 por omisión.
  docker compose -p $P --env-file "$COORD_DIR/coord.env" run --rm --no-deps -T app pytest -n "${SUITE_WORKERS:-8}" --dist worksteal -q > "$COORD_DIR/t$N-suite.log" 2>&1
  RC=$?
  docker compose -p $P --env-file "$COORD_DIR/coord.env" down -v >/dev/null 2>&1
  set -e
  tail -2 "$COORD_DIR/t$N-suite.log"
  if [ $RC -ne 0 ]; then echo "SUITE EN ROJO (código $RC): NO INTEGRAR. Detalle en $COORD_DIR/t$N-suite.log"; exit $RC; fi
fi
git add -A
git commit -q -m "$MSG

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git log --oneline -1
grep -nE "^\| T-$N " "$TASKS"
