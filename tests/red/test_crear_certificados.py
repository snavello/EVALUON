"""La autoridad propia y el certificado del servidor (T-269; REQ-110; ADR-0062).

Corre `scripts/red/crear-certificados.sh` en una carpeta temporal (con `EVALUON_ENV_FILE` y
`EVALUON_RED_DIR`) y revisa con `openssl` lo que hace que la raíz que se instala en las
computadoras de la Comisión no sirva para otra cosa:

- la autoridad es `CA:TRUE` con `pathlen:0` (no puede crear otras autoridades), solo para
  certificados de servidor (`extendedKeyUsage = serverAuth`) y con restricciones de nombre
  críticas de los dos tipos (la IP del equipo, y el nombre de EVALUON o `.invalid`);
- `openssl verify` rechaza lo que esa autoridad no debería poder firmar: otra IP, otro nombre,
  un certificado de cliente o una autoridad intermedia.

Cada propiedad se mira en el texto del certificado y, además, por su efecto en `openssl verify`.
La imagen de la aplicación trae `bash` y OpenSSL 3.5. Las direcciones son de documentación
(192.0.2.0/24) y los nombres terminan en `.example`; las claves y certificados quedan en la
carpeta temporal de pytest.
"""

import itertools
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "red" / "crear-certificados.sh"
SERVER_IP = "192.0.2.10"
NAME = "evaluon.example"

_serials = itertools.count(1000)


def run_script(env_file, red_dir):
    environment = {**os.environ, "EVALUON_ENV_FILE": str(env_file),
                   "EVALUON_RED_DIR": str(red_dir)}
    return subprocess.run(["bash", str(SCRIPT)], env=environment, capture_output=True,
                          encoding="utf-8", timeout=120)


def openssl(*args, check=True):
    return subprocess.run(["openssl", *map(str, args)], capture_output=True, encoding="utf-8",
                          check=check, timeout=60)


def create(folder, address):
    """Corre el script con un `.env` de esa dirección; devuelve la carpeta que escribió."""
    folder.mkdir(parents=True, exist_ok=True)
    env = folder / ".env"
    env.write_text(f"EVALUON_ADDRESS={address}\nEVALUON_SERVER_IP={SERVER_IP}\n",
                   encoding="utf-8")
    red = folder / "red"
    result = run_script(env, red)
    assert result.returncode == 0, result.stdout + result.stderr
    return red


@pytest.fixture(scope="module")
def by_ip(tmp_path_factory):
    return create(tmp_path_factory.mktemp("por-ip"), SERVER_IP)


@pytest.fixture(scope="module")
def by_name(tmp_path_factory):
    return create(tmp_path_factory.mktemp("por-nombre"), NAME)


@pytest.fixture(params=["por-ip", "por-nombre"])
def variant(request, by_ip, by_name):
    """Las dos variantes: (carpeta, nombres permitidos esperados, nombres del servidor)."""
    if request.param == "por-ip":
        return by_ip, ["IP:192.0.2.10/255.255.255.255", "DNS:.invalid"], ["IP Address:192.0.2.10"]
    return (by_name, ["IP:192.0.2.10/255.255.255.255", f"DNS:{NAME}"],
            [f"DNS:{NAME}", "IP Address:192.0.2.10"])


def extensions(certificate):
    """Las extensiones del (primer) certificado del archivo: {nombre: (crítica, [valores])}."""
    text = openssl("x509", "-in", certificate, "-noout", "-text").stdout
    block = text[text.index("X509v3 extensions:"):text.index("Signature Algorithm:",
                                                              text.index("X509v3 extensions:"))]
    result, current = {}, None
    for line in block.splitlines()[1:]:
        header = re.fullmatch(r"\s*X509v3 ([^:]+):\s*(critical)?\s*", line)
        if header:
            current = header.group(1)
            result[current] = (header.group(2) == "critical", [])
        elif current and line.strip():
            result[current][1].append(line.strip())
    return result


def validity_days(certificate):
    dates = openssl("x509", "-in", certificate, "-noout", "-startdate", "-enddate",
                    "-dateopt", "iso_8601").stdout
    start, end = (datetime.strptime(value, "%Y-%m-%d %H:%M:%SZ")
                  for value in re.findall(r"=(.+)", dates))
    return (end - start).days


def sign(authority, work, name, *, san=None, eku="serverAuth", ca=False, issuer=None):
    """Un certificado firmado por `issuer` (por omisión, la autoridad de `authority`)."""
    issuer_crt, issuer_key = issuer or (authority / "autoridad" / "ca-evaluon.crt",
                                        authority / "autoridad" / "ca-evaluon.key")
    lines = ["basicConstraints = critical, CA:TRUE" if ca else "basicConstraints = critical, CA:FALSE",
             "keyUsage = critical, keyCertSign, cRLSign" if ca else "keyUsage = critical, digitalSignature"]
    if san:
        lines.append(f"subjectAltName = {san}")
    if eku:
        lines.append(f"extendedKeyUsage = {eku}")
    work.mkdir(parents=True, exist_ok=True)
    extfile, key, csr, crt = (work / f"{name}{suffix}" for suffix in (".cnf", ".key", ".csr", ".crt"))
    extfile.write_text("[e]\n" + "\n".join(lines) + "\n", encoding="utf-8")
    openssl("genpkey", "-algorithm", "EC", "-pkeyopt", "ec_paramgen_curve:P-256", "-out", key)
    openssl("req", "-new", "-key", key, "-subj", "/O=Prueba", "-out", csr)
    openssl("x509", "-req", "-in", csr, "-CA", issuer_crt, "-CAkey", issuer_key,
            "-set_serial", next(_serials), "-days", "30", "-extfile", extfile, "-extensions", "e",
            "-out", crt)
    return crt, key


def verify(authority, certificate, *extra, purpose="sslserver"):
    result = openssl("verify", "-CAfile", authority / "autoridad" / "ca-evaluon.crt",
                     "-purpose", purpose, *extra, certificate, check=False)
    return result.returncode == 0, result.stdout + result.stderr


# --- La autoridad ---------------------------------------------------------------------------------


def test_the_authority_is_a_server_only_ca_that_cannot_create_other_cas(variant):
    """REQ-110, ADR-0062: la autoridad es `CA:TRUE` con `pathlen:0` (crítica), firma solo
    certificados y listas de revocados, sirve solo para servidores y dura 10 años."""
    red, _, _ = variant
    ca = red / "autoridad" / "ca-evaluon.crt"
    found = extensions(ca)
    assert found["Basic Constraints"] == (True, ["CA:TRUE, pathlen:0"])
    assert found["Key Usage"] == (True, ["Certificate Sign, CRL Sign"])
    assert found["Extended Key Usage"][1] == ["TLS Web Server Authentication"]
    assert validity_days(ca) == 3650


def test_the_authority_is_limited_to_the_evaluon_addresses(variant):
    """REQ-110, ADR-0062: restricciones de nombre críticas de los dos tipos: la IP del equipo y,
    por nombre, solo el de EVALUON; por IP, solo `.invalid` (ningún nombre real)."""
    red, permitted, _ = variant
    critical, values = extensions(red / "autoridad" / "ca-evaluon.crt")["Name Constraints"]
    assert critical
    assert values == ["Permitted:", *permitted]


# --- El certificado del servidor ------------------------------------------------------------------


def test_the_server_certificate_is_for_evaluon_only_and_carries_the_chain(variant):
    """REQ-110: el certificado de Caddy no es autoridad, sirve solo para servidor, nombra la
    dirección de EVALUON y la IP del equipo, no lleva CN (Windows lo controlaría contra las
    restricciones), dura 397 días, va con la autoridad detrás y la autoridad lo acepta."""
    red, _, names = variant
    certificate = red / "certificados" / "evaluon.crt"
    found = extensions(certificate)
    assert found["Basic Constraints"] == (True, ["CA:FALSE"])
    assert found["Extended Key Usage"][1] == ["TLS Web Server Authentication"]
    assert found["Subject Alternative Name"][1] == [", ".join(names)]
    subject = openssl("x509", "-in", certificate, "-noout", "-subject").stdout
    assert "CN" not in subject
    assert validity_days(certificate) == 397
    chain = certificate.read_text(encoding="ascii")
    assert chain.count("BEGIN CERTIFICATE") == 2
    authority = (red / "autoridad" / "ca-evaluon.crt").read_text(encoding="ascii")
    assert chain.endswith(authority)
    assert (red / "ca-evaluon.crt").read_text(encoding="ascii") == authority
    assert "PRIVATE KEY" in (red / "certificados" / "evaluon.key").read_text(encoding="ascii")
    ok, output = verify(red, certificate, "-verify_ip", SERVER_IP)
    assert ok, output


# --- Lo que la autoridad no tiene que poder firmar ------------------------------------------------


@pytest.mark.parametrize("case, san, eku, purpose, error", [
    ("otra-ip", "IP:192.0.2.99", "serverAuth", "sslserver", "permitted subtree violation"),
    ("otro-nombre", "DNS:banco.example", "serverAuth", "sslserver", "permitted subtree violation"),
    ("ip-buena-y-nombre-ajeno", "DNS:banco.example, IP:192.0.2.10", "serverAuth", "sslserver",
     "permitted subtree violation"),
    ("uso-cliente", "IP:192.0.2.10", "clientAuth", "sslclient", "unsuitable certificate purpose"),
])
def test_openssl_rejects_what_the_authority_should_not_sign(by_ip, by_name, tmp_path, case, san,
                                                            eku, purpose, error):
    """REQ-110, ADR-0062: un certificado firmado por la autoridad para otra IP, otro nombre o un
    nombre ajeno junto a la IP buena no vale (restricciones de nombre), y uno de uso cliente
    tampoco (la autoridad es solo de servidor). Con las dos variantes."""
    for red in (by_ip, by_name):
        certificate, _ = sign(red, tmp_path / red.parent.name, case, san=san, eku=eku)
        ok, output = verify(red, certificate, purpose=purpose)
        assert not ok and error in output, (red.parent.name, output)


def test_openssl_accepts_a_certificate_the_authority_may_sign(by_ip, tmp_path):
    """REQ-110: control de las pruebas de rechazo: el mismo procedimiento, para la IP del equipo y
    de servidor, sí vale; los rechazos no vienen de un certificado mal armado."""
    certificate, _ = sign(by_ip, tmp_path, "control", san="IP:192.0.2.10")
    ok, output = verify(by_ip, certificate)
    assert ok, output


def test_openssl_rejects_an_intermediate_authority(by_ip, tmp_path):
    """REQ-110, ADR-0062: con `pathlen:0`, una autoridad intermedia firmada por la de EVALUON no
    puede firmar un certificado válido, aunque sea para la IP del equipo y de servidor."""
    intermediate = sign(by_ip, tmp_path, "intermedia", ca=True)
    certificate, _ = sign(by_ip, tmp_path, "por-la-intermedia", san="IP:192.0.2.10",
                          issuer=intermediate)
    ok, output = verify(by_ip, certificate, "-untrusted", intermediate[0])
    assert not ok and "path length constraint exceeded" in output, output


# --- Renovar y errores ----------------------------------------------------------------------------


def test_running_it_again_renews_the_server_certificate_with_the_same_authority(tmp_path):
    """REQ-110, ADR-0062: volver a correrlo (la renovación anual) conserva la autoridad, así que no
    hay que tocar las computadoras, y cambia la clave del servidor."""
    red = create(tmp_path, SERVER_IP)
    authority = (red / "autoridad" / "ca-evaluon.key").read_bytes()
    server_key = (red / "certificados" / "evaluon.key").read_bytes()

    result = run_script(tmp_path / ".env", red)

    assert result.returncode == 0, result.stderr
    assert (red / "autoridad" / "ca-evaluon.key").read_bytes() == authority
    assert (red / "certificados" / "evaluon.key").read_bytes() != server_key


def test_a_new_address_outside_the_authority_fails_and_keeps_the_previous_certificate(tmp_path):
    """REQ-110: si la dirección cambió y la autoridad no la cubre, el script termina con error,
    dice qué hacer y no pisa el certificado que estaba."""
    red = create(tmp_path, SERVER_IP)
    previous = (red / "certificados" / "evaluon.crt").read_bytes()
    env = tmp_path / "otra.env"
    env.write_text("EVALUON_ADDRESS=192.0.2.11\nEVALUON_SERVER_IP=192.0.2.11\n", encoding="utf-8")

    result = run_script(env, red)

    assert result.returncode == 1
    assert "no cubre 192.0.2.11" in result.stderr
    assert (red / "certificados" / "evaluon.crt").read_bytes() == previous


@pytest.mark.parametrize("env, variable", [
    ("EVALUON_SERVER_IP=192.0.2.10\n", "EVALUON_ADDRESS"),
    ("EVALUON_ADDRESS=https://192.0.2.10\nEVALUON_SERVER_IP=192.0.2.10\n", "EVALUON_ADDRESS"),
    ("EVALUON_ADDRESS=192.0.2.10\nEVALUON_SERVER_IP=192.0.2.256\n", "EVALUON_SERVER_IP"),
    ("EVALUON_ADDRESS=192.0.2.11\nEVALUON_SERVER_IP=192.0.2.10\n", "EVALUON_SERVER_IP"),
])
def test_an_invalid_env_is_rejected_without_creating_anything(tmp_path, env, variable):
    """REQ-110: con el `.env` mal, el script dice qué variable corregir y no crea la carpeta."""
    env_file = tmp_path / ".env"
    env_file.write_text(env, encoding="utf-8")

    result = run_script(env_file, tmp_path / "red")

    assert result.returncode == 1
    assert variable in result.stderr
    assert not (tmp_path / "red").exists()
