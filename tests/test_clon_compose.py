"""Instancia clonada de la feature 016 (T-270; REQ-125; plan 016, «Instancia clonada y ritmo de trabajo»).

`docker-compose.clon.yml` y `scripts/clon.sh` arman un segundo entorno (proyecto `evaluon-016`,
puerto 8016) con su propia base, restaurada de un respaldo de la de trabajo, y su propio motor
del 27B, para medir sin tocar la instancia de 8000. Estas pruebas leen los archivos de la raíz del
repositorio y se saltan los que no están montados en el contenedor (como
`test_instrucciones_revisadas.py`: `docker-compose.yml` no monta `docker-compose.clon.yml` ni
`tools/`; para correrlas todas, montarlos con `-v`). Comprueban:

- la forma del compose: proyecto, servicios con prefijo `clon_`, redes sin salida, un solo puerto
  en 127.0.0.1, motor en un perfil aparte que hereda el comando del archivo del 27B, solo
  `embeddings` y `reranker` de 8000, secretos exigidos y ninguna ruta de un equipo;
- que `scripts/clon.sh` abre y cierra la ventana de GPU en el orden previsto contra un `docker`
  de mentira (sin tocar ningún contenedor), que `--simular` no cambia nada y que si la ventana no se
  puede abrir devuelve 8000 a como estaba;
- `BASE` en `tools/cerrar.sh`, las líneas comentadas de `.env.example` y el documento
  `specs/016-calidad-medible/entorno.md`.

Los datos son sintéticos: nada de esto lee una base ni un caso (P4).
"""

import os
import re
import stat
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
CLON_COMPOSE = ROOT / "docker-compose.clon.yml"
CLON_SCRIPT = ROOT / "scripts" / "clon.sh"
CERRAR = ROOT / "tools" / "cerrar.sh"
ENTORNO = ROOT / "specs" / "016-calidad-medible" / "entorno.md"
ENV_EXAMPLE = ROOT / ".env.example"
BASE_COMPOSE = ROOT / "docker-compose.yml"
QWEN_COMPOSE = ROOT / "docker-compose.qwen38-27b.yml"
REASONING_COMPOSE = ROOT / "docker-compose.razonamiento.yml"
CONSULTA_COMPOSE = ROOT / "docker-compose.consulta-27b.yml"

EXPECTED_SERVICES = {"clon_db", "clon_migrate", "clon_app", "clon_worker", "clon_generation_batch"}


def needs(*paths):
    """Salta la prueba si alguno de los archivos no está montado en este entorno."""
    missing = [p.name for p in paths if not p.is_file()]
    return pytest.mark.skipif(bool(missing), reason=f"no está montado: {', '.join(missing)}")


def load(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def networks_of(service):
    nets = service.get("networks", [])
    return set(nets if isinstance(nets, list) else nets)


# --- forma del compose -----------------------------------------------------------------


@needs(CLON_COMPOSE, BASE_COMPOSE)
def test_the_clone_is_its_own_project_with_prefixed_services():
    """REQ-125: proyecto `evaluon-016`; los cinco servicios llevan el prefijo `clon_` y no repiten el
    nombre de ninguno de la pila real (en la red compartida chocarían); base con volumen propio."""
    clon = load(CLON_COMPOSE)
    base = load(BASE_COMPOSE)
    assert clon["name"] == "evaluon-016"
    assert set(clon["services"]) == EXPECTED_SERVICES
    assert not set(clon["services"]) & set(base["services"])
    assert set(clon["volumes"]) == {"clon_pgdata"}
    assert clon["services"]["clon_db"]["volumes"] == ["clon_pgdata:/var/lib/postgresql/data"]
    assert all("container_name" not in s for s in clon["services"].values())


@needs(CLON_COMPOSE)
def test_the_clone_has_no_internet_and_shares_only_the_ai_network():
    """REQ-125, P4: la base, el motor y el `worker` no tienen salida a internet; la red de la pila real
    (`evaluon_internal`) es externa y solo la usan `clon_app` y `clon_worker`, para llegar a
    `embeddings` y `reranker`; ningún servicio usa la red `egress`."""
    clon = load(CLON_COMPOSE)
    nets = clon["networks"]
    assert nets["clon_internal"] == {"internal": True}
    assert nets["evaluon_internal"] == {"external": True}
    assert "egress" not in nets
    services = clon["services"]
    assert networks_of(services["clon_db"]) == {"clon_internal"}
    assert networks_of(services["clon_generation_batch"]) == {"clon_internal"}
    assert networks_of(services["clon_worker"]) == {"clon_internal", "evaluon_internal"}
    assert networks_of(services["clon_app"]) == {"clon_internal", "evaluon_internal", "clon_web"}
    users = {n for n, s in services.items() if "evaluon_internal" in networks_of(s)}
    assert users == {"clon_app", "clon_worker"}


@needs(CLON_COMPOSE)
def test_only_the_clone_app_publishes_a_port_and_only_on_loopback():
    """REQ-125: el puerto 8016 se publica solo en 127.0.0.1 y solo en `clon_app`."""
    services = load(CLON_COMPOSE)["services"]
    published = {n: s["ports"] for n, s in services.items() if "ports" in s}
    assert published == {"clon_app": ["127.0.0.1:${CLON_PORT:-8016}:8000"]}


@needs(CLON_COMPOSE)
def test_the_clone_reaches_only_embeddings_and_reranker_of_8000_and_its_own_engine():
    """REQ-125: `embeddings` y `reranker` son los de 8000 (por nombre, en la red compartida); la
    generación y los lotes van al motor del clon, nunca a `generation` ni `generation_batch`; la base
    es `clon_db`."""
    env = load(CLON_COMPOSE)["x-clon-app"]["environment"]
    assert env["EMBEDDINGS_URL"] == "http://embeddings:8080"
    assert env["RERANKER_URL"] == "http://reranker:8080"
    assert env["GENERATION_URL"] == "http://clon_generation_batch:8080"
    assert env["GENERATION_BATCH_URL"] == "http://clon_generation_batch:8080"
    assert env["POSTGRES_HOST"] == "clon_db"
    for url in (v for k, v in env.items() if k.endswith("_URL")):
        assert not re.search(r"//(db|generation|generation_batch|app|worker)[:/]", url), url


@needs(CLON_COMPOSE)
def test_secrets_are_required_from_the_env_file_and_no_machine_path_is_written():
    """REQ-125, P4: la contraseña de la base y la clave de Django se exigen del `--env-file` (sin valor
    en el archivo) y ni el compose ni el script llevan la ruta de un equipo: el código, los modelos y
    los casos entran por variables."""
    text = CLON_COMPOSE.read_text(encoding="utf-8")
    assert "${POSTGRES_PASSWORD:?" in text and "${DJANGO_SECRET_KEY:?" in text
    for var in ("CLON_CODE_DIR", "CLON_MODELS_DIR", "CLON_CASOS_DIR"):
        assert "${%s:?" % var in text
    env = load(CLON_COMPOSE)["x-clon-app"]["environment"]
    assert env["POSTGRES_PASSWORD"].startswith("${POSTGRES_PASSWORD:?")
    assert env["DJANGO_SECRET_KEY"].startswith("${DJANGO_SECRET_KEY:?")
    code_lines = [ln for ln in text.splitlines() if not ln.lstrip().startswith("#")]
    if CLON_SCRIPT.is_file():
        code_lines += [ln for ln in CLON_SCRIPT.read_text(encoding="utf-8").splitlines()
                       if not ln.lstrip().startswith("#")]
    for line in code_lines:
        assert not re.search(r"(?<![A-Za-z])[A-Za-z]:[\\/]|/Users/|/home/|/mnt/", line), line


@needs(CLON_COMPOSE)
def test_the_code_is_mounted_read_only_and_only_cases_and_evals_are_writable():
    """REQ-125: el código sale de `CLON_CODE_DIR` en solo lectura (una medición monta una copia fija);
    con escritura solo los casos del clon y `evals/`. El corpus se monta por partes para poder montar
    encima `corpus/casos`."""
    volumes = load(CLON_COMPOSE)["x-clon-app"]["volumes"]
    writable = [v for v in volumes if not v.endswith(":ro")]
    assert writable == ["${CLON_CASOS_DIR:?Falta CLON_CASOS_DIR (archivo de --env-file)}:/app/corpus/casos",
                        "${CLON_CODE_DIR}/evals:/app/evals"]
    targets = {v.split(":/app/", 1)[1].removesuffix(":ro") for v in volumes}
    assert {"evaluon", "tests", "scripts", "manage.py", "pyproject.toml", "specs"} <= targets
    assert "corpus" not in targets and "corpus/normativa" in targets


@needs(CLON_COMPOSE, BASE_COMPOSE, QWEN_COMPOSE, REASONING_COMPOSE)
def test_the_engine_is_the_27b_in_its_own_profile_and_follows_its_sources():
    """REQ-125: `clon_generation_batch` está en el perfil `motor` (`up` sin nombre no lo arranca),
    hereda el `command` y la espera de carga de `docker-compose.qwen38-27b.yml`, usa la imagen, el
    volumen de modelos en solo lectura, la GPU y el chequeo del servicio base, el `entrypoint` del
    archivo de razonamiento, y las variables del modelo de la aplicación son las de ese archivo."""
    clon = load(CLON_COMPOSE)
    engine = clon["services"]["clon_generation_batch"]
    base = load(BASE_COMPOSE)["services"]["generation_batch"]
    qwen = load(QWEN_COMPOSE)
    assert engine["profiles"] == ["motor"]
    assert engine["extends"] == {"file": "docker-compose.qwen38-27b.yml", "service": "generation_batch"}
    assert "command" not in engine and "ports" not in engine
    assert engine["image"] == base["image"]
    assert engine["deploy"] == base["deploy"]
    assert engine["healthcheck"] == {k: v for k, v in base["healthcheck"].items() if k != "start_period"}
    assert engine["volumes"] == ["${CLON_MODELS_DIR:?Falta CLON_MODELS_DIR (archivo de --env-file)}:/models:ro"]
    assert engine["entrypoint"] == load(REASONING_COMPOSE)["services"]["generation_batch"]["entrypoint"]
    assert "--model" in qwen["services"]["generation_batch"]["command"]
    assert qwen["services"]["generation_batch"]["healthcheck"]["start_period"] == "900s"
    # el modelo que registra la aplicación es el del archivo del 27B
    model = qwen["x-qwen38-27b"]
    env = clon["x-clon-app"]["environment"]
    for name, value in model.items():
        assert env[name] == value, name
    consulta = load(CONSULTA_COMPOSE) if CONSULTA_COMPOSE.is_file() else None
    if consulta:
        for name in ("GENERATION_MODEL_ALIAS", "GENERATION_MODEL_FILE", "GENERATION_MODEL_SHA256"):
            assert env[name] == consulta["x-consulta-27b"][name], name


@needs(CLON_COMPOSE)
def test_reasoning_defaults_to_the_contrast_only():
    """REQ-125, REQ-107: sin cambios en el `--env-file`, solo el contraste piensa (`low`), como en
    8000; los demás pasos quedan sin variable. Cada uno se puede mover para una variante."""
    env = load(CLON_COMPOSE)["x-clon-app"]["environment"]
    steps = {k: v for k, v in env.items() if k.startswith("GENERATION_BATCH_REASONING_")}
    assert steps["GENERATION_BATCH_REASONING_CONTRAST"] == "${GENERATION_BATCH_REASONING_CONTRAST:-low}"
    for step in ("EXTRACTION", "COMPLETENESS", "FILTER", "EVALUATION"):
        assert steps[f"GENERATION_BATCH_REASONING_{step}"].endswith(":-}")


@needs(CLON_COMPOSE)
def test_the_clone_services_never_restart_by_themselves():
    """REQ-125: `restart: "no"` en todos; un reinicio de Docker no arranca el motor del clon en medio
    de una ventana de 8000."""
    services = load(CLON_COMPOSE)["services"]
    assert {s["restart"] for s in services.values()} == {"no"}
    assert services["clon_db"]["image"].startswith("pgvector/pgvector:0.8.7-pg17-bookworm@sha256:")


# --- .env.example y documento -------------------------------------------------------------


def test_env_example_lists_the_clone_variables_only_as_comments():
    """REQ-125, P4: `.env.example` dice qué lee el clon pero no define ninguna variable `CLON_*` (van
    en `clon.env`, fuera del repositorio)."""
    lines = ENV_EXAMPLE.read_text(encoding="utf-8").splitlines()
    clon = [ln for ln in lines if "CLON_" in ln]
    assert any(ln.startswith("# CLON_CODE_DIR=") for ln in clon)
    assert all(ln.startswith("#") for ln in clon)
    assert not any(ln.startswith("CLON_") for ln in lines)


@needs(ENTORNO)
def test_the_environment_document_covers_the_clone_runbook():
    """REQ-125: `entorno.md` explica cómo se levanta, se restaura, se abre y cierra una ventana, se
    mide sobre una copia fija y se vuelve atrás, con el ejemplo de la ruta del código."""
    text = ENTORNO.read_text(encoding="utf-8")
    for fragment in (
        "scripts/clon.sh subir", "scripts/clon.sh restaurar", "scripts/clon.sh ventana-abrir",
        "scripts/clon.sh ventana-cerrar", "scripts/clon.sh bajar", "scripts/clon.sh estado",
        "--simular", "git archive", "BASE=016-integracion", "tools/cerrar.sh",
        "C:/Users/snave/Documents/dev/evaluon-wt-016-integracion", "clon.env", "evaluon-016",
        "Volver atrás",
    ):
        assert fragment in text, fragment
    for secret in re.findall(r"(?:PASSWORD|SECRET_KEY)=(\S+)", text):
        assert secret.startswith(("<", "...", "***")), secret


# --- tools/cerrar.sh: BASE ---------------------------------------------------------------------


@needs(CERRAR)
def test_cerrar_integrates_the_base_branch_and_defaults_to_main():
    """REQ-125: `tools/cerrar.sh` lee `BASE` (por omisión `main`, comportamiento de siempre) y con
    `BASE=016-integracion` integra `origin/016-integracion`; no queda ningún `origin/main` fijo en
    las órdenes."""
    text = CERRAR.read_text(encoding="utf-8")
    assert "BASE=${BASE:-main}" in text
    commands = [ln for ln in text.splitlines() if not ln.lstrip().startswith("#")]
    assert not any("origin/main" in ln for ln in commands)
    assert any('merge "origin/$BASE"' in ln for ln in commands)
    assert any('--is-ancestor "origin/$BASE" HEAD' in ln for ln in commands)
    assert any('"origin/$BASE" -- $CODE' in ln for ln in commands)
    # con BASE=main los mensajes son los de siempre
    assert 'echo "FALTA ${BASE^^}"' in text
    assert "gestión: integra $BASE en" in text


@needs(CERRAR)
def test_cerrar_still_parses():
    """REQ-125: la sintaxis de `tools/cerrar.sh` es válida."""
    subprocess.run(["bash", "-n", str(CERRAR)], check=True)


# --- scripts/clon.sh: sintaxis y ventana de GPU contra un docker de mentira ------------------------

STUB_DOCKER = r"""#!/usr/bin/env bash
# docker de mentira (tests/test_clon_compose.py): registra cada llamada y contesta con el estado de
# los archivos de $STUB_STATE. No toca ningún contenedor.
S="$STUB_STATE"
echo "$*" >> "$S/calls.log"
args=" $* "
svc_id() { case "$1" in generation_batch) echo gbid;; worker) echo wkid;; app) echo appid;;
    db) echo dbid;; embeddings) echo embid;; reranker) echo rerid;; clon_generation_batch) echo ceid;; esac; }
name_of() { case "$1" in gbid) echo evaluon-generation_batch-1;; wkid) echo evaluon-worker-1;;
    appid) echo evaluon-app-1;; dbid) echo evaluon-db-1;; embid) echo evaluon-embeddings-1;;
    rerid) echo evaluon-reranker-1;; ceid) echo evaluon-016-clon_generation_batch-1;;
    otroid) echo evaluon-t999-motor-ajeno;; esac; }
id_of_name() { case "$1" in evaluon-generation_batch-1) echo gbid;; evaluon-worker-1) echo wkid;;
    evaluon-app-1) echo appid;; evaluon-db-1) echo dbid;; evaluon-016-clon_generation_batch-1) echo ceid;; *) echo "$1";; esac; }
running() { [ -f "$S/run_$1" ]; }
cmd="$1"; shift
case "$cmd" in
  network|image|volume) exit 0 ;;
  ps)
    if [[ "$args" == *"ancestor="* ]]; then
      for i in gbid embid rerid ceid otroid; do running $i && echo "$i"; done; exit 0
    fi
    [[ "$args" =~ service=([a-z_]+) ]] && id="$(svc_id "${BASH_REMATCH[1]}")"
    if [[ "$args" == *" -a "* ]] || running "$id"; then echo "$id"; fi
    exit 0 ;;
  inspect)
    fmt="$2"; id="$(id_of_name "$3")"
    case "$fmt" in
      *State.Running*) running "$id" && echo true || echo false ;;
      *State.Health*) running "$id" && echo healthy || echo unhealthy ;;
      *.Name*) echo "/$(name_of "$id")" ;;
    esac
    exit 0 ;;
  exec)
    shift_args=("$@"); id=""
    for a in "${shift_args[@]}"; do case "$a" in -*) ;; *) id="$a"; break ;; esac; done
    if [[ "$args" == *"/health"* ]]; then echo '{"status":"ok"}'
    elif [[ "$args" == *"/props"* ]]; then echo "{\"model_alias\":\"$(cat "$S/alias" )\",\"n_ctx\":32768}"
    elif [[ "$args" == *"printenv GENERATION_BATCH_MODEL_ALIAS"* ]]; then cat "$S/app_alias"
    elif [[ "$args" == *"printenv GENERATION_BATCH_CTX_SIZE"* ]]; then echo 32768
    else cat > /dev/null; cat "$S/cola"; fi
    exit 0 ;;
  stop) id="$(id_of_name "${@: -1}")"; rm -f "$S/run_$id"; exit 0 ;;
  start) id="$(id_of_name "${@: -1}")"; touch "$S/run_$id"; exit 0 ;;
  compose)
    if [[ "$args" == *" rm "* ]]; then rm -f "$S/run_ceid" "$S/ce_created"
    elif [[ "$args" == *" up "* ]]; then
      touch "$S/ce_created"
      [ -f "$S/motor_falla" ] || touch "$S/run_ceid"
    elif [[ "$args" == *" ps "* ]]; then [ -f "$S/ce_created" ] && echo ceid
    elif [[ "$args" == *" exec "* ]]; then cat > /dev/null; echo 0
    fi
    exit 0 ;;
esac
exit 0
"""

STUB_CURL = """#!/usr/bin/env bash
echo 200
"""

STUB_NVIDIA = """#!/usr/bin/env bash
if [ -f "$STUB_STATE/run_gbid" ]; then cat "$STUB_STATE/gpu_before"; else cat "$STUB_STATE/gpu_after"; fi
"""

MUTATING = re.compile(r"^(stop|start)\b|^compose .* (up|rm|run|down|stop) ")


class Window:
    """Un `docker` de mentira con el estado de una instancia de 8000 sana y la ventana cerrada."""

    def __init__(self, tmp_path):
        self.state = tmp_path / "state"
        self.state.mkdir()
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        for name, body in (("docker", STUB_DOCKER), ("curl", STUB_CURL), ("nvidia-smi", STUB_NVIDIA)):
            path = bin_dir / name
            path.write_text(body, encoding="utf-8", newline="\n")
            path.chmod(path.stat().st_mode | stat.S_IEXEC)
        coord = tmp_path / "coord"
        coord.mkdir()
        models = tmp_path / "models"
        models.mkdir()
        for gguf in ("Qwen3.8-27B-UD-Q4_K_M.gguf", "mmproj-Qwen3.8-27B-F16.gguf"):
            (models / gguf).write_bytes(b"x")
        (coord / "clon.env").write_text(
            f"POSTGRES_PASSWORD=sintetica\nDJANGO_SECRET_KEY=sintetica\nCLON_PORT=8016\n"
            f"CLON_CODE_DIR={tmp_path}\nCLON_MODELS_DIR={models}\nCLON_CASOS_DIR={tmp_path / 'casos'}\n",
            encoding="utf-8")
        for running in ("gbid", "wkid", "appid", "dbid", "embid", "rerid"):
            (self.state / f"run_{running}").touch()
        (self.state / "alias").write_text("qwen3.8-27b-ud-q4_k_m")
        (self.state / "app_alias").write_text("qwen3.8-27b-ud-q4_k_m")
        (self.state / "cola").write_text("0\n")
        (self.state / "gpu_before").write_text("21000\n")
        (self.state / "gpu_after").write_text("2500\n")
        self.env = {
            **os.environ,
            "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
            "STUB_STATE": str(self.state),
            "COORD_DIR": str(coord),
            "CLON_PAUSA_GPU": "0",
            "CLON_ESPERA_MOTOR": "2",
        }
        self.env.pop("CLON_ENV_FILE", None)

    def run(self, *args):
        return subprocess.run(["bash", str(CLON_SCRIPT), *args], env=self.env, cwd=ROOT,
                              capture_output=True, text=True, timeout=60)

    def calls(self):
        log = self.state / "calls.log"
        return log.read_text(encoding="utf-8").splitlines() if log.exists() else []

    def running(self, key):
        return (self.state / f"run_{key}").exists()


@pytest.fixture
def window(tmp_path):
    return Window(tmp_path)


@needs(CLON_SCRIPT)
def test_the_script_parses_and_lists_every_subcommand():
    """REQ-125: `scripts/clon.sh` tiene sintaxis válida y su ayuda nombra las siete órdenes."""
    subprocess.run(["bash", "-n", str(CLON_SCRIPT)], check=True)
    header = "\n".join(CLON_SCRIPT.read_text(encoding="utf-8").splitlines()[:14])
    for order in ("subir", "restaurar", "ventana-abrir", "ventana-cerrar", "bajar", "estado", "ejecutar"):
        assert f"scripts/clon.sh {order}" in header, order
    assert "--simular" in header and "DRY_RUN" in header


@needs(CLON_SCRIPT)
def test_simulated_window_changes_nothing(window):
    """REQ-125: `ventana-abrir --simular` y `ventana-cerrar --simular` (y `DRY_RUN=1`) dicen lo que
    harían, comprueban las condiciones y no detienen, arrancan, crean ni quitan nada."""
    opened = window.run("ventana-abrir", "--simular")
    assert opened.returncode == 0, opened.stdout + opened.stderr
    assert "[simular] haría: docker stop -t 120 evaluon-worker-1" in opened.stdout
    assert "[simular] haría: docker stop -t 120 evaluon-generation_batch-1" in opened.stdout
    assert "clon_generation_batch" in opened.stdout and "la cola de 8000 está vacía" in opened.stdout
    window.env["DRY_RUN"] = "1"
    closed = window.run("ventana-cerrar")
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert "/health del motor: ok" in closed.stdout and "cola vacía" in closed.stdout
    assert not [c for c in window.calls() if MUTATING.search(c)], window.calls()
    assert all(window.running(k) for k in ("gbid", "wkid", "appid", "dbid", "embid", "rerid"))
    assert not window.running("ceid")


@needs(CLON_SCRIPT)
def test_open_stops_the_worker_then_the_engine_then_starts_the_clone_engine(window):
    """REQ-125: `ventana-abrir` detiene primero el `worker` y después el motor de 8000, comprueba la
    GPU y arranca `clon_generation_batch`; `embeddings` y `reranker` de 8000 no se tocan."""
    result = window.run("ventana-abrir")
    assert result.returncode == 0, result.stdout + result.stderr
    calls = window.calls()
    stop_worker = calls.index("stop -t 120 evaluon-worker-1")
    stop_engine = calls.index("stop -t 120 evaluon-generation_batch-1")
    up = next(i for i, c in enumerate(calls) if c.startswith("compose") and " up " in c)
    assert stop_worker < stop_engine < up
    assert "clon_generation_batch" in calls[up] and "--no-deps" in calls[up]
    assert not any("embeddings" in c or "reranker" in c for c in calls if MUTATING.search(c))
    assert not window.running("gbid") and not window.running("wkid") and window.running("ceid")
    assert window.running("embid") and window.running("rerid") and window.running("appid")


@needs(CLON_SCRIPT)
def test_open_refuses_when_the_queue_is_not_empty(window):
    """REQ-125: con pedidos en espera o en curso en 8000 la ventana no se abre y no se detiene nada."""
    (window.state / "cola").write_text("2\n")
    result = window.run("ventana-abrir")
    assert result.returncode != 0
    assert "la cola de 8000 tiene 2 pedido(s)" in result.stdout
    assert not [c for c in window.calls() if MUTATING.search(c)]
    assert window.running("gbid") and window.running("wkid")


@needs(CLON_SCRIPT)
def test_open_refuses_when_the_window_is_already_open(window):
    """REQ-125: con el motor del clon ya en marcha no se abre otra ventana y no se detiene nada."""
    (window.state / "run_ceid").touch()
    (window.state / "ce_created").touch()
    result = window.run("ventana-abrir")
    assert result.returncode != 0
    assert "el motor del clon ya está en marcha" in result.stdout
    assert not [c for c in window.calls() if MUTATING.search(c)]


@needs(CLON_SCRIPT)
def test_open_refuses_when_another_engine_uses_the_gpu(window):
    """REQ-125: un motor ajeno en marcha (imagen de llama.cpp que no es el de lotes, `embeddings` ni
    `reranker` de 8000, por ejemplo uno de una medición vieja) impide abrir y no se detiene nada."""
    (window.state / "run_otroid").touch()
    result = window.run("ventana-abrir")
    assert result.returncode != 0
    assert "otros motores en marcha: evaluon-t999-motor-ajeno" in result.stdout
    assert not [c for c in window.calls() if MUTATING.search(c)]


@needs(CLON_SCRIPT)
def test_open_gives_8000_back_if_the_gpu_stays_busy(window):
    """REQ-125: si con el motor de 8000 detenido la GPU sigue ocupada, no se arranca el motor del clon
    y 8000 vuelve a estar en marcha."""
    (window.state / "gpu_after").write_text("20000\n")
    result = window.run("ventana-abrir")
    assert result.returncode != 0
    assert window.running("gbid") and window.running("wkid") and not window.running("ceid")
    assert not any(c.startswith("compose") and " up " in c for c in window.calls())


@needs(CLON_SCRIPT)
def test_open_gives_8000_back_if_the_clone_engine_does_not_start(window):
    """REQ-125: si el motor del clon no queda sano, se lo baja y se devuelve 8000 a como estaba."""
    (window.state / "motor_falla").touch()
    result = window.run("ventana-abrir")
    assert result.returncode != 0
    assert window.running("gbid") and window.running("wkid") and not window.running("ceid")
    assert any(c.startswith("start ") for c in window.calls())


@needs(CLON_SCRIPT)
def test_close_brings_the_clone_engine_down_and_checks_8000(window):
    """REQ-125: `ventana-cerrar` baja el motor del clon, arranca el motor y el `worker` de 8000 y
    comprueba `/health`, `/props` (alias y contexto que registra la aplicación), cola vacía y
    `/ingresar/` 200."""
    assert window.run("ventana-abrir").returncode == 0
    result = window.run("ventana-cerrar")
    assert result.returncode == 0, result.stdout + result.stderr
    assert not window.running("ceid") and window.running("gbid") and window.running("wkid")
    for line in ("/health del motor: ok", "n_ctx 32768", "cola vacía", "/ingresar/ 200", "worker en marcha"):
        assert line in result.stdout, line
    assert "FALLA" not in result.stdout


@needs(CLON_SCRIPT)
def test_close_fails_when_8000_does_not_come_back_as_registered(window):
    """REQ-125: si el motor devuelto no es el que registra la aplicación, o la cola no está vacía,
    `ventana-cerrar` sale con error y lo dice."""
    assert window.run("ventana-abrir").returncode == 0
    (window.state / "alias").write_text("otro-modelo")
    (window.state / "cola").write_text("1\n")
    result = window.run("ventana-cerrar")
    assert result.returncode != 0
    assert "FALLA  /props del motor" in result.stdout and "FALLA  cola con 1 pedido(s)" in result.stdout
