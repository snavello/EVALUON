"""`docker-compose.razonamiento.yml`: permitir al servidor el razonamiento propio del modelo y
pasar a la aplicación el de cada paso (T-253; REQ-107; ADR-0056, enmienda del 2026-10-11).

El archivo se suma, al final, a cualquiera de los otros (`docker-compose.yml`, el del 26B-A4B y los
de los candidatos Qwen). Un `command` de Compose no se combina con el de otro archivo, así que el
archivo no lo repite: cambia el `entrypoint` para que `llama-server` reciba, después de todas las
banderas, `--reasoning auto --reasoning-budget -1`; con una bandera repetida, el servidor usa la
última (avisa `argument '--reasoning' specified multiple times ... only last value will be used`,
verificado con la compilación b11347). Estas pruebas comprueban el archivo y, con un `sh` real, que
el `command` de cada archivo termina con esas dos banderas y sigue igual en todo lo demás.

Se prueba sin modelo ni GPU (P4).
"""

import subprocess
from pathlib import Path

import pytest
import yaml
from django.conf import settings

REPO = Path(settings.BASE_DIR)
FILE = REPO / "docker-compose.razonamiento.yml"
SUMMED_TO = ("docker-compose.yml", "docker-compose.modelo-grande.yml",
             "docker-compose.qwen38-27b.yml", "docker-compose.qwen36-35b.yml")
STEPS = ("extraction", "completeness", "filter", "evaluation", "contrast")


@pytest.fixture(scope="module")
def reasoning():
    assert FILE.is_file(), f"No se encuentra {FILE}: tiene que estar montado en app"
    return yaml.safe_load(FILE.read_text(encoding="utf-8"))


def _command(name):
    data = yaml.safe_load((REPO / name).read_text(encoding="utf-8"))
    return [str(item) for item in data["services"]["generation_batch"]["command"]]


def _last_value(args, flag):
    """El valor que tomaría `llama-server`: el de la última aparición de `flag`."""
    last = None
    for position, item in enumerate(args[:-1]):
        if item == flag:
            last = args[position + 1]
    return last


def _run_entrypoint(reasoning, args, tmp_path):
    """Corre el `entrypoint` del archivo con un `sh` real y `args` como `command`, sustituyendo el
    `llama-server` por un programa que imprime sus argumentos de a uno por línea."""
    entrypoint = [str(item) for item in reasoning["services"]["generation_batch"]["entrypoint"]]
    assert entrypoint[:2] == ["/bin/sh", "-c"]
    script = entrypoint[2].replace("$$", "$").replace("/app/llama-server", str(tmp_path / "fake"))
    fake = tmp_path / "fake"
    fake.write_text('#!/bin/sh\nfor a in "$@"; do printf "%s\\n" "$a"; done\n')
    fake.chmod(0o755)
    done = subprocess.run(["/bin/sh", "-c", script, *entrypoint[3:], *args],
                          capture_output=True, text=True, check=True)
    return done.stdout.splitlines()


def test_the_file_only_changes_the_batch_engine_entrypoint_and_the_app_environment(reasoning):
    """REQ-107, P4: el archivo no cambia la imagen, el `command`, los puertos ni las redes del
    motor (sigue en la red interna, sin salida): solo su `entrypoint`; a `app` y `worker` les suma
    variables de entorno."""
    assert set(reasoning["services"]) == {"generation_batch", "worker", "app"}
    assert set(reasoning["services"]["generation_batch"]) == {"entrypoint"}
    for service in ("worker", "app"):
        assert set(reasoning["services"][service]) == {"environment"}


@pytest.mark.parametrize("name", SUMMED_TO)
def test_it_adds_the_flags_at_the_end_of_any_other_file(reasoning, tmp_path, name):
    """REQ-107: sumado a cualquier otro archivo, `llama-server` recibe todo el `command` de ese
    archivo, sin cambios, y al final `--reasoning auto --reasoning-budget -1`: la última bandera
    gana sobre el `--reasoning off --reasoning-budget 0` de arriba."""
    command = _command(name)
    assert _last_value(command, "--reasoning") == "off"
    assert _last_value(command, "--reasoning-budget") == "0"
    received = _run_entrypoint(reasoning, command, tmp_path)
    assert received[:len(command)] == command
    assert received[len(command):] == ["--reasoning", "auto", "--reasoning-budget", "-1"]
    assert _last_value(received, "--reasoning") == "auto"
    assert _last_value(received, "--reasoning-budget") == "-1"


def test_the_flags_of_the_base_stay_off_without_the_file():
    """REQ-107: sin este archivo, el motor de lotes del compose base sigue sin razonamiento."""
    command = _command("docker-compose.yml")
    assert _last_value(command, "--reasoning") == "off"
    assert _last_value(command, "--reasoning-budget") == "0"


def test_app_and_worker_receive_the_variables_of_every_step(reasoning):
    """REQ-107: `app` y `worker` reciben, vacías por omisión (el paso queda apagado), la variable de
    cada paso, el tope de cada nivel y la espera extra; los nombres son los que lee `settings.py`."""
    env = reasoning["services"]["app"]["environment"]
    assert env == reasoning["services"]["worker"]["environment"]
    expected = {f"GENERATION_BATCH_REASONING_{step.upper()}" for step in STEPS}
    expected |= {f"GENERATION_BATCH_REASONING_BUDGET_{level}" for level in ("LOW", "MEDIUM", "HIGH")}
    expected.add("GENERATION_BATCH_REASONING_EXTRA_TIMEOUT_SECONDS")
    assert set(env) == expected
    assert tuple(settings.GENERATION_BATCH_REASONING_STEPS) == STEPS
    for name, value in env.items():
        assert value == "${" + name + ":-}", name  # sin variable, vacía: vale la de settings.py


def test_the_file_is_mounted_in_the_app_for_these_tests():
    """REQ-107: `docker-compose.yml` monta este archivo en la aplicación, solo para que estas
    pruebas lo lean."""
    base = yaml.safe_load((REPO / "docker-compose.yml").read_text(encoding="utf-8"))
    line = "./docker-compose.razonamiento.yml:/app/docker-compose.razonamiento.yml:ro"
    for volumes in (base["x-app"]["volumes"], base["services"]["app"]["volumes"]):
        assert line in volumes


# --- T-254 · configuración candidata: el 27B con razonamiento solo en el contraste ---------------

ENTORNO = REPO / "specs" / "015-uso-y-eleccion-del-modelo" / "entorno.md"
CANDIDATE_COMMAND = ("GENERATION_BATCH_REASONING_CONTRAST=low docker compose "
                     "-f docker-compose.yml -f docker-compose.qwen38-27b.yml "
                     "-f docker-compose.razonamiento.yml up -d --no-deps generation_batch worker app")


def test_only_the_contrast_thinks_with_the_candidate_variable():
    """REQ-107: con `GENERATION_BATCH_REASONING_CONTRAST=low` y nada más, solo el contraste de la
    evaluación piensa, con nivel `low`; los otros cuatro pasos quedan apagados."""
    from evaluon import settings as project_settings

    levels = project_settings.reasoning_levels({"GENERATION_BATCH_REASONING_CONTRAST": "low"})

    assert levels == {"extraction": "off", "completeness": "off", "filter": "off",
                      "evaluation": "off", "contrast": "low"}


def test_the_candidate_configuration_is_documented_and_its_files_exist():
    """REQ-107 (T-254): `entorno.md` dice cómo se levanta el Qwen3.8-27B con razonamiento solo en
    el contraste: el compose del 27B, más el de razonamiento, más la variable del contraste en
    `low`, y cómo volver al 12B; los archivos y los pasos que nombra existen. Sin esos
    comandos escritos, la configuración candidata no se puede reproducir (P5)."""
    if not ENTORNO.is_file():
        pytest.skip("specs/ no está montada en este entorno: montarla para comprobar el documento")
    text = ENTORNO.read_text(encoding="utf-8")

    assert "## Configuración candidata" in text
    section = text[text.index("## Configuración candidata"):]
    assert CANDIDATE_COMMAND in section
    assert "docker compose -f docker-compose.yml up -d --no-deps generation_batch worker app" in section
    assert "docker compose stop generation" in section
    for name in ("docker-compose.qwen38-27b.yml", "docker-compose.razonamiento.yml"):
        assert (REPO / name).is_file()
    assert "contrast" in settings.GENERATION_BATCH_REASONING_STEPS
    # lo que se pierde mientras está levantado y el tiempo de carga medido
    assert "propuesta de datos del procedimiento" in section and "desde T-247 pide al motor de lotes" in section
    assert "4,5 minutos" in section


def test_the_default_use_is_documented_with_the_way_back():
    """REQ-107 (T-247, T-255): `entorno.md` dice cómo se instala desde cero con el 27B por omisión
    (`.env`, descarga de los modelos, `docker compose up -d`), la memoria, los tiempos y la carga
    medidos, qué pasa con la Consulta y con el alta desde el pliego, y cómo se vuelve al 12B. La
    combinación de `COMPOSE_FILE` que dice es la de `.env.example`: con `consulta-27b` (T-255)."""
    if not ENTORNO.is_file():
        pytest.skip("specs/ no está montada en este entorno: montarla para comprobar el documento")
    text = ENTORNO.read_text(encoding="utf-8")

    assert "## Uso por omisión" in text
    section = text[text.index("## Uso por omisión"):]
    for needed in (
            "cp .env.example .env", "bash scripts/fetch_models.sh --qwen38-27b", "docker compose up -d",
            "COMPOSE_FILE=docker-compose.yml:docker-compose.qwen38-27b.yml:docker-compose.razonamiento.yml"
            ":docker-compose.consulta-27b.yml", "COMPOSE_PATH_SEPARATOR=:",
            "GENERATION_BATCH_REASONING_CONTRAST=low", "20.956 MiB", "72,9 min", "3 min 4 s",
            "`start_period` del chequeo a 900 s",
            "no está disponible por ahora", "Cómo se vuelve al 12B",
            "docker compose -f docker-compose.yml up -d --no-deps generation_batch worker app generation"):
        assert needed in section, needed
    # la combinación por omisión del documento es la que trae `.env.example`
    env_example = (REPO / ".env.example").read_text(encoding="utf-8").splitlines()
    [compose_file] = [line for line in env_example if line.startswith("COMPOSE_FILE=")]
    assert compose_file in section
    assert ":docker-compose.sin-consulta.yml" not in compose_file


def test_the_consulta_in_the_27b_is_documented():
    """REQ-107 (T-255): `entorno.md` tiene la sección de la Consulta en el motor del 27B, con su estado
    (preparado, sin desplegar), qué cambia respecto del 27B sin Consulta, los avisos con las palabras
    exactas del código, cómo se despliega y se comprueba, y cómo se vuelve (al 27B sin Consulta y al
    12B). Si el texto de un aviso cambia en el código, el documento tiene que decir lo mismo."""
    if not ENTORNO.is_file():
        pytest.skip("specs/ no está montada en este entorno: montarla para comprobar el documento")
    from evaluon.queries import services

    text = ENTORNO.read_text(encoding="utf-8")
    title = "## La Consulta en el motor del 27B (T-255, ADR-0057)"
    assert title in text
    section = text[text.index(title):].split("\n## ", 1)[0]  # hasta la sección siguiente

    for needed in (
            "Estado: preparado, sin desplegar", "docker-compose.consulta-27b.yml",
            "docker-compose.sin-consulta.yml", "GENERATION_CTX_SIZE", "### Qué cambia",
            "### Cómo se comporta", "### Desplegar y comprobar", "### Cómo se vuelve",
            "### Prueba de humo contra el motor real", "Cómo se vuelve al 12B",
            services.BUSY_NOTICE, services.NOT_RESPONDING_NOTICE):
        assert needed in section, needed
    # del texto de T-247, que sigue con `generation` aparte, el documento cita lo que lo distingue
    fragment = "el equipo usa el modelo grande para las evaluaciones y deja apagado el motor de la consulta"
    assert fragment in section and fragment in services.UNAVAILABLE_NOTICE


def test_the_smoke_test_of_the_consulta_in_the_27b_is_documented_with_its_numbers():
    """REQ-107 (T-255): `entorno.md` deja la prueba de humo de la Consulta contra el motor real
    (2026-10-13), ya hecha: los casos con su tiempo, el registro (P6), que no hubo razonamiento,
    `/health` respondiendo mientras genera, los avisos contra el motor real y la comparación con el
    12B. El texto de espera que propone es el que dicen la pantalla de la Consulta y la pestaña."""
    if not ENTORNO.is_file():
        pytest.skip("specs/ no está montada en este entorno: montarla para comprobar el documento")
    text = ENTORNO.read_text(encoding="utf-8")
    title = "### Prueba de humo contra el motor real"
    assert title in text
    smoke = text[text.index(title):].split("\n## ", 1)[0]  # hasta la sección siguiente

    assert "Pendiente" not in smoke
    for needed in (
            "2026-10-13", "EV-002", "EV-013", "EV-014", "EV-033", "34,0 s",  # los casos y el total
            "`parameters.generation`", "`generation_batch`", "qwen3.8-27b-ud-q4_k_m",  # P6
            "enable_thinking", "`reasoning_content`",  # sin razonamiento
            "`/health`", "31 de 31",  # la salud mientras genera
            "20.997 MiB",  # la memoria de video no cambia
            "Comparación con el 12B", "corridas guardadas del 2026-10-03",
            "no se apagó el motor de 8000"):  # lo que no se probó contra el motor real
        assert needed in smoke, needed
    from evaluon.queries import services
    assert services.BUSY_NOTICE in smoke
    # el texto de espera que dice el documento es el de las dos plantillas
    wait = "Puede tardar hasta un minuto"
    assert wait in smoke
    for template in ("queries/consulta.html", "journey/temas/s5_consulta.html"):
        html = (REPO / "evaluon" / "templates" / template).read_text(encoding="utf-8")
        assert wait in html and "medio minuto" not in html, template
