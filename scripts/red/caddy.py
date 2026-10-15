"""Arma el Caddyfile del acceso por red desde el .env (plan 007, T-269; REQ-109, REQ-110, REQ-116).

Lee del .env:

- EVALUON_ADDRESS: el nombre o la IPv4 con que se entra a EVALUON;
- EVALUON_SERVER_IP: la IPv4 fija de este equipo;
- EVALUON_COMPUTERS: las computadoras autorizadas, `nombre=IPv4` separadas por comas, 10 como
  máximo y sin repetidos;
- APP_PORT: el puerto local de la aplicación (8000 si falta, como en docker-compose.yml);
- DJANGO_ALLOWED_HOSTS: tiene que incluir EVALUON_ADDRESS.

Si algo está mal, dice qué corregir y no escribe nada. Si está bien, escribe `<carpeta>/Caddyfile`
desde `Caddyfile.plantilla` (ADR-0061). Lo corre `aplicar-red.ps1` con el Python del equipo, fuera
de Docker: usa solo la biblioteca estándar.

Uso, desde la raíz del repositorio:

    py -3 scripts/red/caddy.py [--env .env] [--carpeta C:\\EVALUON-red] [--json]

Con `--json` informa la dirección, la lista y las direcciones que pasan (las de la regla del
firewall) en una línea JSON, para el script de PowerShell.
"""

import argparse
import ipaddress
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from string import Template

MAX_COMPUTERS = 10
SYSTEM_COMPUTER = "equipo-del-sistema"
DEFAULT_FOLDER = r"C:\EVALUON-red"
DEFAULT_APP_PORT = 8000
REPO = Path(__file__).resolve().parents[2]
TEMPLATE = Path(__file__).with_name("Caddyfile.plantilla")

# Nombre de una computadora: va al Caddyfile y al registro de accesos.
COMPUTER_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,62}")
# Nombre del DNS (RFC 1123): etiquetas de letras, números y guiones, separadas por puntos.
DNS_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")
LOOKS_LIKE_IP = re.compile(r"[0-9./]+")
IPV4_EXAMPLE = "cuatro números del 0 al 255 separados por puntos, por ejemplo 192.0.2.10"


class InvalidNetworkConfig(Exception):
    def __init__(self, errors):
        super().__init__("\n".join(errors))
        self.errors = errors


@dataclass(frozen=True)
class NetworkConfig:
    address: str
    address_is_ip: bool
    server_ip: str
    computers: tuple  # ((nombre, IPv4), ...), en el orden del .env
    app_port: int

    @property
    def allowed_ips(self):
        """Las direcciones que pasan: el equipo y la lista."""
        return [self.server_ip, *(ip for _, ip in self.computers)]


def read_env(text):
    """Las variables de un .env, como las lee Docker Compose: `NOMBRE=valor` por línea, con
    comentarios (#), comillas y comentario al final de la línea. Si una variable se repite, vale
    la última."""
    values = {}
    for raw in text.lstrip("\ufeff").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        name, sep, value = line.partition("=")
        if not sep:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        else:
            value = re.split(r"\s+#", value, maxsplit=1)[0].strip()
        values[name.strip()] = value
    return values


def _ipv4(text):
    """La IPv4 de una computadora de la red, o None si no lo es."""
    try:
        ip = ipaddress.IPv4Address(text)
    except ValueError:
        return None
    if ip.is_unspecified or ip.is_loopback or ip.is_multicast or ip == ipaddress.IPv4Address(
            "255.255.255.255"):
        return None
    return str(ip)


def _dns_name(text):
    name = text.lower().rstrip(".")
    if not name or len(name) > 253 or LOOKS_LIKE_IP.fullmatch(name):
        return None
    if all(DNS_LABEL.fullmatch(label) for label in name.split(".")):
        return name
    return None


def load(values):
    """La configuración de red validada a partir de las variables del .env. Junta todos los
    errores y los informa juntos (InvalidNetworkConfig), en lenguaje llano."""
    errors = []

    address_text = values.get("EVALUON_ADDRESS", "").strip()
    address, address_is_ip = None, False
    if not address_text:
        errors.append("Falta EVALUON_ADDRESS en el .env: la dirección con que se entra a EVALUON "
                      "(un nombre del DNS interno o la IPv4 fija de este equipo).")
    elif _ipv4(address_text):
        address, address_is_ip = _ipv4(address_text), True
    elif _dns_name(address_text):
        address = _dns_name(address_text)
    else:
        errors.append(f"EVALUON_ADDRESS «{address_text}» no es un nombre ni una IPv4 válidos: "
                      f"poner solo el nombre (sin https://) o la IPv4 ({IPV4_EXAMPLE}).")

    server_text = values.get("EVALUON_SERVER_IP", "").strip()
    server_ip = _ipv4(server_text)
    if not server_text:
        errors.append("Falta EVALUON_SERVER_IP en el .env: la IPv4 fija de este equipo.")
    elif not server_ip:
        errors.append(f"EVALUON_SERVER_IP «{server_text}» no es la IPv4 de un equipo de la red "
                      f"({IPV4_EXAMPLE}).")
    if address_is_ip and server_ip and address != server_ip:
        errors.append(f"EVALUON_ADDRESS es la IPv4 {address} y EVALUON_SERVER_IP es {server_ip}: "
                      "si se entra por IP, es la del propio equipo; poner la misma en las dos.")

    computers, seen_names, seen_ips = [], {}, {}
    entries = [entry.strip() for entry in values.get("EVALUON_COMPUTERS", "").split(",")]
    for entry in (entry for entry in entries if entry):
        name, sep, ip_text = (part.strip() for part in entry.partition("="))
        if not sep or not name or not ip_text:
            errors.append(f"EVALUON_COMPUTERS: «{entry}» no tiene la forma nombre=dirección "
                          "(por ejemplo comision-1=192.0.2.21).")
            continue
        ip = _ipv4(ip_text)
        if not COMPUTER_NAME.fullmatch(name):
            errors.append(f"EVALUON_COMPUTERS: el nombre «{name}» no sirve: usar letras sin "
                          "acentos, números, guiones, puntos o guiones bajos, sin espacios, "
                          "empezando por letra o número y hasta 63 caracteres.")
        elif name.lower() == SYSTEM_COMPUTER:
            errors.append(f"EVALUON_COMPUTERS: el nombre {SYSTEM_COMPUTER} es del propio equipo; "
                          "usar otro.")
        elif name.lower() in seen_names:
            errors.append(f"EVALUON_COMPUTERS: el nombre «{name}» está repetido (ya está "
                          f"«{seen_names[name.lower()]}»).")
        if not ip:
            errors.append(f"EVALUON_COMPUTERS: «{name}» tiene la dirección «{ip_text}», que no es "
                          f"la IPv4 de una computadora de la red ({IPV4_EXAMPLE}).")
        elif server_ip and ip == server_ip:
            errors.append(f"EVALUON_COMPUTERS: «{name}» tiene la dirección del propio equipo "
                          f"(EVALUON_SERVER_IP); el equipo ya entra siempre, como "
                          f"{SYSTEM_COMPUTER}: sacarlo de la lista.")
        elif ip in seen_ips:
            errors.append(f"EVALUON_COMPUTERS: la dirección {ip} está repetida (en «{seen_ips[ip]}» "
                          f"y en «{name}»).")
        seen_names.setdefault(name.lower(), name)
        if ip:
            seen_ips.setdefault(ip, name)
        computers.append((name, ip))
    if len(computers) > MAX_COMPUTERS:
        errors.append(f"EVALUON_COMPUTERS tiene {len(computers)} computadoras: el máximo es "
                      f"{MAX_COMPUTERS}.")

    port_text = values.get("APP_PORT", "").strip()
    app_port = DEFAULT_APP_PORT
    if port_text:
        app_port = int(port_text) if port_text.isdigit() else 0
        if not 1 <= app_port <= 65535:
            errors.append(f"APP_PORT «{port_text}» no es un puerto válido (un número del 1 al "
                          "65535; si falta, 8000).")

    if address:
        hosts = [host.strip().lower() for host in values.get("DJANGO_ALLOWED_HOSTS", "").split(",")]
        if address not in hosts:
            errors.append(f"DJANGO_ALLOWED_HOSTS no incluye {address}: agregarla al final, "
                          "separada por una coma (por ejemplo DJANGO_ALLOWED_HOSTS=localhost,"
                          f"127.0.0.1,{address}), y recrear la aplicación (docker compose up -d); "
                          "si no, la aplicación rechaza los pedidos que llegan por esa dirección.")

    if errors:
        raise InvalidNetworkConfig(errors)
    return NetworkConfig(address=address, address_is_ip=address_is_ip, server_ip=server_ip,
                         computers=tuple(computers), app_port=app_port)


def certificate_paths(folder):
    """Los dos archivos del certificado (ADR-0062), con barras `/`, como los lee Caddy."""
    base = PureWindowsPath(folder).as_posix().rstrip("/")
    return f"{base}/certificados/evaluon.crt", f"{base}/certificados/evaluon.key"


def render(config, folder=DEFAULT_FOLDER):
    """El texto del Caddyfile para `config`, con el certificado de `folder`."""
    certificate, key = certificate_paths(folder)
    mapping = [(config.server_ip, SYSTEM_COMPUTER), *((ip, name) for name, ip in config.computers)]
    if config.address_is_ip:
        default_sni = f"\tdefault_sni {config.address}"
    else:
        default_sni = "\t# Sin default_sni: se entra por nombre y el navegador lo manda."
    template = Template(TEMPLATE.read_text(encoding="utf-8"))
    return template.substitute(
        address=config.address,
        allowed_ips=" ".join(config.allowed_ips),
        default_sni=default_sni,
        certificate=certificate,
        key=key,
        computer_map="\n".join(f'\t\t\t{ip} "{name}"' for ip, name in mapping),
        app_port=config.app_port,
    )


def report(config, caddyfile):
    return {
        "address": config.address,
        "server_ip": config.server_ip,
        "computers": [{"name": name, "ip": ip} for name, ip in config.computers],
        "allowed_ips": config.allowed_ips,
        "app_port": config.app_port,
        "caddyfile": str(caddyfile),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Arma el Caddyfile de EVALUON desde el .env.")
    parser.add_argument("--env", default=str(REPO / ".env"), help="el .env (por omisión, el de "
                        "la raíz del repositorio)")
    parser.add_argument("--carpeta", default=DEFAULT_FOLDER, help="la carpeta de Caddy y del "
                        f"certificado (por omisión, {DEFAULT_FOLDER})")
    parser.add_argument("--json", action="store_true", help="informar en JSON, para "
                        "aplicar-red.ps1")
    args = parser.parse_args(argv)

    env_file = Path(args.env)
    if not env_file.is_file():
        print(f"No se encontró el .env en {env_file}.", file=sys.stderr)
        return 1
    try:
        config = load(read_env(env_file.read_text(encoding="utf-8-sig")))
    except InvalidNetworkConfig as invalid:
        print("Hay que corregir el .env:", file=sys.stderr)
        for error in invalid.errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    folder = Path(args.carpeta)
    missing = [name for name in ("evaluon.crt", "evaluon.key")
               if not (folder / "certificados" / name).is_file()]
    if missing:
        print(f"Faltan los archivos del certificado en {folder / 'certificados'}: "
              f"{' y '.join(missing)}. Crearlos con «bash scripts/red/crear-certificados.sh» "
              "(Git Bash, en la raíz del repositorio) o copiar ahí los del área de sistemas con "
              "esos dos nombres.", file=sys.stderr)
        return 1

    caddyfile = folder / "Caddyfile"
    caddyfile.write_text(render(config, args.carpeta), encoding="utf-8", newline="\n")

    if args.json:
        print(json.dumps(report(config, caddyfile)))
    else:
        print(f"Caddyfile escrito en {caddyfile}.")
        print(f"Dirección: https://{config.address}")
        print(f"Equipo del sistema: {config.server_ip}")
        print(f"Computadoras de la lista ({len(config.computers)}):")
        for name, ip in config.computers:
            print(f"  {name}  {ip}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
