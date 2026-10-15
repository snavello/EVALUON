"""El Caddyfile del acceso por red (T-269; REQ-109, REQ-110, REQ-116).

`scripts/red/caddy.py` lee el `.env`, valida la dirección de EVALUON, la IP del equipo, la lista de
computadoras y el puerto de la aplicación, y escribe el `Caddyfile` desde
`scripts/red/Caddyfile.plantilla` (plan 007, «Componentes»; ADR-0061). Estas pruebas no corren Caddy
ni tocan la red: comparan el texto que sale. Que Caddy lo acepte se comprobó con `caddy adapt`
(entorno.md, «Comprobaciones de T-269»).

Todas las direcciones son de documentación (192.0.2.0/24, RFC 5737) y los nombres terminan en
`.example` (RFC 2606): ninguna es de la red del organismo.
"""

import importlib.util
import ipaddress
import json
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "red" / "caddy.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("evaluon_red_caddy", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


caddy = _load_script()

DOCUMENTATION_NET = ipaddress.ip_network("192.0.2.0/24")

VALID = {
    "EVALUON_ADDRESS": "192.0.2.10",
    "EVALUON_SERVER_IP": "192.0.2.10",
    "EVALUON_COMPUTERS": "comision-1=192.0.2.21, comision-2=192.0.2.22",
    "APP_PORT": "8000",
    "DJANGO_ALLOWED_HOSTS": "localhost,127.0.0.1,192.0.2.10",
}

# Lo que tiene que quedar del Caddyfile de VALID, sin comentarios, líneas en blanco ni sangría.
EXPECTED_DIRECTIVES = [
    "{",
    "admin off",
    "auto_https off",
    "default_sni 192.0.2.10",
    "}",
    "http://192.0.2.10 {",
    "@fuera_de_la_lista not remote_ip 192.0.2.10 192.0.2.21 192.0.2.22",
    "route {",
    "abort @fuera_de_la_lista",
    "redir https://192.0.2.10{uri} 308",
    "}",
    "}",
    "https://192.0.2.10 {",
    'tls "C:/EVALUON-red/certificados/evaluon.crt" "C:/EVALUON-red/certificados/evaluon.key"',
    "@fuera_de_la_lista not remote_ip 192.0.2.10 192.0.2.21 192.0.2.22",
    "route {",
    "abort @fuera_de_la_lista",
    "map {remote_host} {evaluon_computer} {",
    '192.0.2.10 "equipo-del-sistema"',
    '192.0.2.21 "comision-1"',
    '192.0.2.22 "comision-2"',
    "}",
    "reverse_proxy 127.0.0.1:8000 {",
    "header_up X-Evaluon-Computer {evaluon_computer}",
    "}",
    "}",
    "}",
]


def values(**changes):
    result = dict(VALID)
    for name, value in changes.items():
        if value is None:
            result.pop(name, None)
        else:
            result[name] = value
    return result


def render(**changes):
    return caddy.render(caddy.load(values(**changes)), r"C:\EVALUON-red")


def directives(text):
    """Las líneas con algo para Caddy: sin comentarios ni líneas en blanco, sin sangría."""
    lines = (line.strip() for line in text.splitlines())
    return [line for line in lines if line and not line.startswith("#")]


def errors_for(**changes):
    with pytest.raises(caddy.InvalidNetworkConfig) as raised:
        caddy.load(values(**changes))
    return raised.value.errors


def site(text, address):
    """Las directivas de un sitio del Caddyfile, desde su encabezado hasta su llave de cierre."""
    lines = directives(text)
    body = []
    for line in lines[lines.index(f"{address} {{"):]:
        body.append(line)
        if _balanced(body):
            return body
    raise AssertionError(f"sin cierre para {address}")


def _balanced(lines):
    """Cuenta solo las llaves de bloque: las de los marcadores como `{uri}` no abren nada."""
    depth = 0
    for line in lines:
        bare = re.sub(r"\{[a-z_.]+\}", "", line)
        depth += bare.count("{") - bare.count("}")
    return depth == 0 and len(lines) > 1


# --- Una lista válida ------------------------------------------------------------------------------


def test_a_valid_list_gives_the_expected_caddyfile():
    """REQ-109, REQ-110, REQ-116: con una dirección, el equipo y dos computadoras, el Caddyfile es
    el esperado, directiva por directiva."""
    assert directives(render()) == EXPECTED_DIRECTIVES


def test_the_system_computer_enters_as_equipo_del_sistema():
    """REQ-109: la IP del equipo está en la lista de las que pasan, en los dos sitios, y su nombre
    para la aplicación es `equipo-del-sistema`, aunque la lista de computadoras esté vacía."""
    text = render(EVALUON_COMPUTERS="")
    assert caddy.SYSTEM_COMPUTER == "equipo-del-sistema"
    assert directives(text).count("@fuera_de_la_lista not remote_ip 192.0.2.10") == 2
    assert '192.0.2.10 "equipo-del-sistema"' in directives(text)


def test_admin_api_and_automatic_https_are_off():
    """REQ-116: sin la API de administración local (puerto 2019, que no pide clave) ni
    certificados o redirecciones automáticas: lo que hace Caddy está escrito en el archivo."""
    lines = directives(render())
    global_block = lines[: lines.index("}") + 1]
    assert global_block[0] == "{"
    assert "admin off" in global_block
    assert "auto_https off" in global_block


def test_default_sni_only_when_entering_by_ip():
    """REQ-110: si se entra por IP el navegador no manda nombre (SNI) y Caddy necesita
    `default_sni` para darle el certificado; si se entra por nombre, no hace falta."""
    assert "default_sni 192.0.2.10" in directives(render())
    by_name = render(EVALUON_ADDRESS="evaluon.example",
                     DJANGO_ALLOWED_HOSTS="localhost,127.0.0.1,evaluon.example")
    assert not [line for line in directives(by_name) if line.startswith("default_sni")]
    assert "http://evaluon.example {" in directives(by_name)
    assert "https://evaluon.example {" in directives(by_name)


def test_the_plain_http_site_cuts_and_redirects_without_content():
    """REQ-109, REQ-110: el sitio sin cifrar primero corta lo que no viene de la lista y después
    redirige con 308 a la misma dirección cifrada; no reenvía nada a la aplicación ni responde
    contenido. `route` mantiene ese orden (sin él, Caddy pone `redir` antes que `abort`)."""
    body = site(render(), "http://192.0.2.10")
    assert body == [
        "http://192.0.2.10 {",
        "@fuera_de_la_lista not remote_ip 192.0.2.10 192.0.2.21 192.0.2.22",
        "route {",
        "abort @fuera_de_la_lista",
        "redir https://192.0.2.10{uri} 308",
        "}",
        "}",
    ]
    assert not [line for line in body if line.split()[0] in ("reverse_proxy", "respond",
                                                             "file_server")]


def test_the_https_site_cuts_first_and_forwards_only_to_the_local_app():
    """REQ-109, REQ-110, REQ-116: el sitio cifrado usa los dos archivos del certificado de la
    carpeta, corta lo que no viene de la lista antes de nada y reenvía solo a
    `127.0.0.1:<APP_PORT>`, con el nombre de la computadora en `X-Evaluon-Computer`."""
    body = site(render(APP_PORT="8123"), "https://192.0.2.10")
    assert body[1].startswith('tls "C:/EVALUON-red/certificados/evaluon.crt" ')
    route = body[body.index("route {") + 1:]
    assert route[0] == "abort @fuera_de_la_lista"
    proxies = [line for line in body if line.startswith("reverse_proxy")]
    assert proxies == ["reverse_proxy 127.0.0.1:8123 {"]
    assert "header_up X-Evaluon-Computer {evaluon_computer}" in body


def test_there_are_no_external_hosts():
    """REQ-116, P4: el Caddyfile no nombra ningún host fuera del equipo y la lista: ni autoridades
    de certificados, ni servidores a los que reenviar, ni direcciones que no sean la de EVALUON,
    la del equipo, las de la lista o `127.0.0.1`."""
    for changes in ({}, {"EVALUON_ADDRESS": "evaluon.example",
                         "DJANGO_ALLOWED_HOSTS": "evaluon.example"}):
        text = "\n".join(directives(render(**changes)))
        address = changes.get("EVALUON_ADDRESS", "192.0.2.10")
        ips = set(re.findall(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", text))
        assert ips <= {"127.0.0.1", "192.0.2.10", "192.0.2.21", "192.0.2.22"}
        urls = set(re.findall(r"\b[a-z]+://([^\s/{]+)", text))
        assert urls == {address}
        names = set(re.findall(r"\b(?:[a-z0-9-]+\.)+[a-z]{2,}\b", text.lower()))
        assert names <= {address, "evaluon.crt", "evaluon.key"}
        for word in ("acme", "email", "issuer", "on_demand", "internal", "ca_root", "import"):
            assert not re.search(rf"\b{word}\b", text), word


def test_names_are_written_lowercase():
    """REQ-109: la dirección por nombre se escribe en minúsculas (el navegador la manda así)."""
    config = caddy.load(values(EVALUON_ADDRESS="EVALUON.Example",
                               DJANGO_ALLOWED_HOSTS="evaluon.example"))
    assert config.address == "evaluon.example"
    assert not config.address_is_ip


# --- Lo que se rechaza ------------------------------------------------------------------------------


def test_eleven_computers_are_rejected():
    """REQ-109: la lista tiene 10 computadoras como máximo (spec, requisitos no funcionales)."""
    ten = ",".join(f"pc-{n}=192.0.2.{20 + n}" for n in range(1, 11))
    assert len(caddy.load(values(EVALUON_COMPUTERS=ten)).computers) == 10
    errors = errors_for(EVALUON_COMPUTERS=ten + ",pc-11=192.0.2.31")
    assert any("11" in error and "10" in error for error in errors), errors


@pytest.mark.parametrize("computers, fragment", [
    ("pc-a=192.0.2.21,pc-b=192.0.2.21", "192.0.2.21"),
    ("pc-a=192.0.2.21,pc-a=192.0.2.22", "pc-a"),
    ("pc-a=192.0.2.21,PC-A=192.0.2.22", "PC-A"),
])
def test_repeated_computers_are_rejected(computers, fragment):
    """REQ-109: ni direcciones ni nombres repetidos en la lista."""
    errors = errors_for(EVALUON_COMPUTERS=computers)
    assert any("repetid" in error and fragment in error for error in errors), errors


@pytest.mark.parametrize("computers", [
    "pc-a=192.0.2.300",
    "pc-a=192.0.2",
    "pc-a=192.0.2.0/24",
    "pc-a=192.0.02.21",
    "pc-a=pc-a.example",
    "pc-a=",
    "pc-a",
    "=192.0.2.21",
    "pc-a=0.0.0.0",
    "pc-a=127.0.0.1",
    "pc-a=255.255.255.255",
    "pc-a=224.0.0.1",
])
def test_invalid_computer_addresses_are_rejected(computers):
    """REQ-109: cada computadora va como `nombre=IPv4`, con la IPv4 de una computadora."""
    assert errors_for(EVALUON_COMPUTERS=computers)


@pytest.mark.parametrize("name", [
    "pc a", "pc}", 'pc"a', "pc{x}", "ñandú", "-pc", "x" * 64, "equipo-del-sistema",
])
def test_invalid_or_reserved_computer_names_are_rejected(name):
    """REQ-109: el nombre va al Caddyfile y al registro de accesos: letras sin acentos, números,
    guiones, puntos y guiones bajos, hasta 63; `equipo-del-sistema` es del propio equipo."""
    assert errors_for(EVALUON_COMPUTERS=f"{name}=192.0.2.21")


def test_the_system_ip_cannot_be_a_listed_computer():
    """REQ-109: el equipo ya entra como `equipo-del-sistema`; ponerlo en la lista con otro nombre
    lo repetiría."""
    errors = errors_for(EVALUON_COMPUTERS="pc-a=192.0.2.10")
    assert any("EVALUON_SERVER_IP" in error for error in errors), errors


@pytest.mark.parametrize("changes, variable", [
    ({"EVALUON_ADDRESS": None}, "EVALUON_ADDRESS"),
    ({"EVALUON_ADDRESS": ""}, "EVALUON_ADDRESS"),
    ({"EVALUON_ADDRESS": "https://192.0.2.10"}, "EVALUON_ADDRESS"),
    ({"EVALUON_ADDRESS": "evaluon_red.example"}, "EVALUON_ADDRESS"),
    ({"EVALUON_ADDRESS": "192.0.2.300"}, "EVALUON_ADDRESS"),
    ({"EVALUON_ADDRESS": "192.0.2.11"}, "EVALUON_ADDRESS"),
    ({"EVALUON_SERVER_IP": None}, "EVALUON_SERVER_IP"),
    ({"EVALUON_SERVER_IP": "evaluon.example"}, "EVALUON_SERVER_IP"),
    ({"EVALUON_SERVER_IP": "127.0.0.1", "EVALUON_ADDRESS": "evaluon.example",
      "DJANGO_ALLOWED_HOSTS": "evaluon.example"}, "EVALUON_SERVER_IP"),
    ({"APP_PORT": "0"}, "APP_PORT"),
    ({"APP_PORT": "70000"}, "APP_PORT"),
    ({"APP_PORT": "ocho mil"}, "APP_PORT"),
    ({"DJANGO_ALLOWED_HOSTS": "localhost,127.0.0.1"}, "DJANGO_ALLOWED_HOSTS"),
    ({"DJANGO_ALLOWED_HOSTS": None}, "DJANGO_ALLOWED_HOSTS"),
])
def test_invalid_variables_are_rejected_naming_the_variable(changes, variable):
    """REQ-109: cada error dice qué variable del `.env` corregir. Por IP, la dirección es la del
    equipo; la dirección tiene que estar en DJANGO_ALLOWED_HOSTS (si no, la aplicación rechaza
    todos los pedidos)."""
    errors = errors_for(**changes)
    assert any(variable in error for error in errors), errors


def test_app_port_defaults_to_8000():
    """REQ-109: sin APP_PORT en el `.env`, el de docker-compose.yml: 8000."""
    assert caddy.load(values(APP_PORT=None)).app_port == 8000


def test_every_error_is_reported_at_once():
    """REQ-109: con varias cosas mal, se ven todas juntas, para corregirlas de una vez."""
    errors = errors_for(EVALUON_SERVER_IP="x", APP_PORT="x", EVALUON_COMPUTERS="pc a=1")
    assert len(errors) >= 3


# --- El .env ---------------------------------------------------------------------------------------


def test_read_env_understands_the_dotenv_format():
    """REQ-109: el `.env` se lee como lo lee Docker Compose: comentarios, comillas, comentario al
    final de la línea, fin de línea de Windows y marca de orden de bytes."""
    text = (
        "\ufeff# comentario\r\n"
        "EVALUON_ADDRESS=192.0.2.10\r\n"
        'EVALUON_SERVER_IP="192.0.2.10"\r\n'
        "EVALUON_COMPUTERS='comision-1=192.0.2.21'\r\n"
        "APP_PORT=8000 # puerto\r\n"
        "\r\n"
        "# EVALUON_ADDRESS=192.0.2.99\r\n"
        "SIN_VALOR=\r\n"
    )
    assert caddy.read_env(text) == {
        "EVALUON_ADDRESS": "192.0.2.10",
        "EVALUON_SERVER_IP": "192.0.2.10",
        "EVALUON_COMPUTERS": "comision-1=192.0.2.21",
        "APP_PORT": "8000",
        "SIN_VALOR": "",
    }


def test_the_env_example_block_is_valid_and_uses_documentation_addresses():
    """REQ-109, P4: el bloque «Acceso por red (plan 007)» de `.env.example` trae las tres variables
    y la dirección en DJANGO_ALLOWED_HOSTS, comentadas; descomentadas son válidas y solo usan
    direcciones de documentación."""
    text = (REPO / ".env.example").read_text(encoding="utf-8")
    block = text[text.index("Acceso por red (plan 007)"):]
    example = {}
    for line in block.splitlines():
        found = re.fullmatch(r"#\s*(EVALUON_\w+|DJANGO_ALLOWED_HOSTS)=(.*)", line.strip())
        if found:
            example.setdefault(found.group(1), found.group(2))
    assert set(example) == {"EVALUON_ADDRESS", "EVALUON_SERVER_IP", "EVALUON_COMPUTERS",
                            "DJANGO_ALLOWED_HOSTS"}
    config = caddy.load(example)
    assert config.computers
    for ip in (config.server_ip, *(ip for _, ip in config.computers)):
        assert ipaddress.ip_address(ip) in DOCUMENTATION_NET
    # ninguna asignación sin comentar: sin el bloque, EVALUON sigue solo en el equipo
    assert not re.search(r"^EVALUON_", text, re.MULTILINE)


# --- Lo que usa aplicar-red.ps1 --------------------------------------------------------------------


def test_the_pinned_caddy_is_the_windows_zip_of_2_11_7():
    """REQ-110, P5: `caddy.sha512` es la línea de las sumas publicadas del zip de Windows de la
    versión fijada en el ADR-0061 (2.11.7): de ahí sale la versión que baja `aplicar-red.ps1`."""
    lines = (REPO / "scripts" / "red" / "caddy.sha512").read_text(encoding="ascii").splitlines()
    assert len(lines) == 1
    assert re.fullmatch(r"[0-9a-f]{128}  caddy_2\.11\.7_windows_amd64\.zip", lines[0])


def test_the_admin_script_is_utf8_with_bom_and_applies_the_rule_from_the_list():
    """REQ-109, REQ-116: `aplicar-red.ps1` está en UTF-8 con marca de orden de bytes (Windows
    PowerShell lee mal los acentos sin ella), pide administrador, comprueba la suma con SHA-512 y
    arma la regla de entrada con TCP 80 y 443, solo `caddy.exe`, solo las direcciones que informa
    `caddy.py` y en todos los perfiles."""
    raw = (REPO / "scripts" / "red" / "aplicar-red.ps1").read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig")
    assert text.startswith("#Requires -RunAsAdministrator")
    assert "Get-FileHash -Algorithm SHA512" in text
    rule = text[text.index("New-NetFirewallRule"):].split("| Out-Null")[0]
    for part in ("-Direction Inbound", "-Action Allow", "-Protocol TCP", "-LocalPort 80, 443",
                 "-Program $Caddy", "-RemoteAddress $permitidas", "-Profile Any"):
        assert part in rule, part
    assert "$permitidas = @($red.allowed_ips)" in text


# --- El comando ------------------------------------------------------------------------------------


def write_env(path, **changes):
    path.write_text("".join(f"{name}={value}\n" for name, value in values(**changes).items()),
                    encoding="utf-8")


def make_certificates(folder):
    (folder / "certificados").mkdir(parents=True)
    (folder / "certificados" / "evaluon.crt").write_text("certificado de prueba")
    (folder / "certificados" / "evaluon.key").write_text("clave de prueba")


def test_the_command_writes_the_caddyfile_and_reports_the_list(tmp_path, capsys):
    """REQ-109: el comando escribe `Caddyfile` en la carpeta y con `--json` informa la dirección y
    las direcciones que deja pasar, para la regla del firewall."""
    env, folder = tmp_path / ".env", tmp_path / "red"
    write_env(env)
    make_certificates(folder)

    assert caddy.main(["--env", str(env), "--carpeta", str(folder), "--json"]) == 0

    report = json.loads(capsys.readouterr().out)
    assert report["address"] == "192.0.2.10"
    assert report["allowed_ips"] == ["192.0.2.10", "192.0.2.21", "192.0.2.22"]
    assert report["computers"] == [{"name": "comision-1", "ip": "192.0.2.21"},
                                   {"name": "comision-2", "ip": "192.0.2.22"}]
    written = (folder / "Caddyfile").read_text(encoding="utf-8")
    assert f'tls "{folder.as_posix()}/certificados/evaluon.crt"' in written
    assert "\r" not in written


def test_the_command_rejects_an_invalid_env_without_writing(tmp_path, capsys):
    """REQ-109: con el `.env` mal, el comando termina con error, dice qué corregir y no escribe."""
    env, folder = tmp_path / ".env", tmp_path / "red"
    write_env(env, EVALUON_COMPUTERS="pc-a=192.0.2.300")
    make_certificates(folder)

    assert caddy.main(["--env", str(env), "--carpeta", str(folder)]) == 1

    assert "EVALUON_COMPUTERS" in capsys.readouterr().err
    assert not (folder / "Caddyfile").exists()


def test_the_command_asks_for_the_certificates(tmp_path, capsys):
    """REQ-110: sin los dos archivos del certificado, el comando lo dice y cómo crearlos."""
    env, folder = tmp_path / ".env", tmp_path / "red"
    write_env(env)
    folder.mkdir()

    assert caddy.main(["--env", str(env), "--carpeta", str(folder)]) == 1

    assert "crear-certificados.sh" in capsys.readouterr().err
    assert not (folder / "Caddyfile").exists()
