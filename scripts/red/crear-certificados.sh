#!/usr/bin/env bash
# Crea la autoridad propia de EVALUON, si falta, y el certificado del servidor
# (plan 007, T-269; REQ-110; ADR-0062, variante B).
#
# Se corre en Git Bash, desde la raíz del repositorio, después de completar el .env:
#   bash scripts/red/crear-certificados.sh
# Usa el openssl de Git para Windows. Lee EVALUON_ADDRESS y EVALUON_SERVER_IP del .env y escribe
# en C:\EVALUON-red\ (fuera del repositorio; nada de esto se sube):
#   autoridad\ca-evaluon.key, ca-evaluon.crt  la autoridad: 10 años; solo firma certificados de
#                                             servidor y solo para la dirección de EVALUON y la
#                                             del equipo. Se usa solo para renovar.
#   certificados\evaluon.crt, evaluon.key     el del servidor: 397 días, con la cadena; lo lee Caddy.
#   ca-evaluon.crt                            la raíz, para instalar una vez en cada computadora.
# Volver a correrlo renueva el certificado del servidor con la misma autoridad: no hay que tocar
# las computadoras. Si se usa el certificado del área de sistemas (variante A), no correrlo: pisa
# certificados\evaluon.crt y evaluon.key.
#
# Opcionales: EVALUON_ENV_FILE (otro .env) y EVALUON_RED_DIR (otra carpeta, para probar).
set -euo pipefail
# Sin esto, Git Bash convierte "/CN=..." en una ruta de Windows.
export MSYS_NO_PATHCONV=1

REPO=$(cd "$(dirname "$0")/../.." && pwd)
ENV_FILE=${EVALUON_ENV_FILE:-$REPO/.env}
RED_DIR=${EVALUON_RED_DIR:-C:/EVALUON-red}

die() { echo "ERROR: $*" >&2; exit 1; }

# Corre openssl sin mostrar sus avisos; si falla, muestra lo que dijo y termina.
quiet() {
  local out
  out=$("$@" 2>&1) || { printf '%s
' "$out" >&2; die "falló openssl $2."; }
}

# Ruta con barras / que entienden openssl (de Windows) y las herramientas de Git Bash.
winpath() { if command -v cygpath >/dev/null 2>&1; then cygpath -m "$1"; else printf '%s' "$1"; fi; }

# Último valor de la variable $1 en el .env, sin comillas ni comentario al final.
env_value() {
  local line value=""
  while IFS= read -r line || [ -n "$line" ]; do
    line=${line%$'\r'}
    line=${line#$'\xEF\xBB\xBF'}
    case $line in "$1="*) value=${line#"$1="} ;; esac
  done < "$ENV_FILE"
  value=$(printf '%s' "$value" | sed -E -e 's/^[[:space:]]+//' -e 's/[[:space:]]+#.*$//' \
    -e 's/[[:space:]]+$//' -e 's/^"(.*)"$/\1/' -e "s/^'(.*)'\$/\\1/")
  printf '%s' "$value"
}

is_ipv4() {
  local IFS=. part
  [[ $1 =~ ^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$ ]] || return 1
  for part in $1; do
    [[ $part =~ ^(0|[1-9][0-9]*)$ ]] && [ "$part" -le 255 ] || return 1
  done
}

is_dns_name() {
  [ ${#1} -le 253 ] && [[ ! $1 =~ ^[0-9.]+$ ]] &&
    [[ $1 =~ ^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)*$ ]]
}

command -v openssl >/dev/null 2>&1 || die "No se encontró openssl: correr este script en Git Bash."
[ -f "$ENV_FILE" ] || die "No se encontró el .env en $ENV_FILE."

ADDRESS=$(env_value EVALUON_ADDRESS | tr 'A-Z' 'a-z')
SERVER_IP=$(env_value EVALUON_SERVER_IP)
[ -n "$ADDRESS" ] || die "Falta EVALUON_ADDRESS en el .env (ver specs/007-acceso-por-red/entorno.md)."
[ -n "$SERVER_IP" ] || die "Falta EVALUON_SERVER_IP en el .env."
is_ipv4 "$SERVER_IP" || die "EVALUON_SERVER_IP «$SERVER_IP» no es una IPv4 (por ejemplo 192.0.2.10)."
if is_ipv4 "$ADDRESS"; then
  [ "$ADDRESS" = "$SERVER_IP" ] ||
    die "EVALUON_ADDRESS es una IPv4 distinta de EVALUON_SERVER_IP: si se entra por IP, es la del equipo."
  ADDRESS_IS_IP=1
else
  is_dns_name "$ADDRESS" ||
    die "EVALUON_ADDRESS «$ADDRESS» no es un nombre ni una IPv4 válidos (poner solo el nombre, sin https://)."
  ADDRESS_IS_IP=0
fi

mkdir -p "$RED_DIR/autoridad" "$RED_DIR/certificados"
RED=$(winpath "$RED_DIR")
CA_KEY=$RED/autoridad/ca-evaluon.key
CA_CRT=$RED/autoridad/ca-evaluon.crt
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
W=$(winpath "$WORK")

# Restricciones de la autoridad: solo las IP de EVALUON y del equipo, y el nombre de EVALUON (o
# .invalid si se entra por IP, para que no sirva para ningún nombre). Nombres alternativos del
# certificado del servidor: la dirección y la IP del equipo.
if [ "$ADDRESS_IS_IP" = 1 ]; then
  CONSTRAINTS="permitted;IP.1 = $SERVER_IP/255.255.255.255
permitted;DNS.1 = .invalid"
  NAMES="IP.1 = $SERVER_IP"
else
  CONSTRAINTS="permitted;IP.1 = $SERVER_IP/255.255.255.255
permitted;DNS.1 = $ADDRESS"
  NAMES="DNS.1 = $ADDRESS
IP.1 = $SERVER_IP"
fi

cat > "$WORK/openssl.cnf" <<EOF
[req]
distinguished_name = dn
prompt = no
[dn]
CN = EVALUON
[ca_ext]
basicConstraints = critical, CA:TRUE, pathlen:0
keyUsage = critical, keyCertSign, cRLSign
extendedKeyUsage = serverAuth
nameConstraints = critical, @constraints
subjectKeyIdentifier = hash
[constraints]
$CONSTRAINTS
[server_ext]
basicConstraints = critical, CA:FALSE
keyUsage = critical, digitalSignature
extendedKeyUsage = serverAuth
subjectAltName = @names
subjectKeyIdentifier = hash
authorityKeyIdentifier = keyid
[names]
$NAMES
EOF

if [ -f "$CA_KEY" ] && [ -f "$CA_CRT" ]; then
  echo "Autoridad: se usa la que ya está en $RED/autoridad (para renovar no se crea otra)."
else
  [ ! -f "$CA_KEY" ] && [ ! -f "$CA_CRT" ] ||
    die "En $RED/autoridad hay solo uno de los dos archivos de la autoridad: borrar la carpeta y volver a correr."
  echo "Creando la autoridad propia de EVALUON (10 años)..."
  quiet openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:P-256 -out "$W/ca.key"
  quiet openssl req -new -x509 -sha256 -days 3650 -key "$W/ca.key" -config "$W/openssl.cnf" \
    -subj "/O=EVALUON/CN=EVALUON autoridad propia" -extensions ca_ext -out "$W/ca.crt"
  mv "$WORK/ca.key" "$RED_DIR/autoridad/ca-evaluon.key"
  mv "$WORK/ca.crt" "$RED_DIR/autoridad/ca-evaluon.crt"
fi

echo "Creando el certificado del servidor para $ADDRESS (397 días)..."
# Sin CN: Windows controla el CN contra las restricciones de nombre de la autoridad y rechaza el
# certificado (probado con Schannel, error 0x4000). Los navegadores leen solo los nombres
# alternativos.
quiet openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:P-256 -out "$W/evaluon.key"
quiet openssl req -new -sha256 -key "$W/evaluon.key" -config "$W/openssl.cnf" \
  -subj "/O=EVALUON" -out "$W/evaluon.csr"
quiet openssl x509 -req -sha256 -days 397 -in "$W/evaluon.csr" -CA "$CA_CRT" -CAkey "$CA_KEY" \
  -set_serial "0x$(openssl rand -hex 16)" -extfile "$W/openssl.cnf" -extensions server_ext \
  -out "$W/servidor.crt"

# La autoridad tiene que aceptar el certificado: si la dirección cambió y queda fuera de sus
# restricciones, hay que crear otra autoridad y volver a instalar la raíz.
if ! openssl verify -CAfile "$CA_CRT" -purpose sslserver "$W/servidor.crt" >/dev/null 2>&1; then
  die "La autoridad de $RED/autoridad no cubre $ADDRESS (¿cambió la dirección?). Borrar esa carpeta, volver a correr este script e instalar la raíz nueva en cada computadora."
fi

cat "$WORK/servidor.crt" "$RED_DIR/autoridad/ca-evaluon.crt" > "$WORK/evaluon.crt"
mv "$WORK/evaluon.crt" "$RED_DIR/certificados/evaluon.crt"
mv "$WORK/evaluon.key" "$RED_DIR/certificados/evaluon.key"
cp "$RED_DIR/autoridad/ca-evaluon.crt" "$RED_DIR/ca-evaluon.crt"

hex() { sed -e 's/^.*=//' -e 's/://g' | tr 'A-F' 'a-f'; }
echo
echo "Listo. En $RED:"
echo "  certificados/evaluon.crt y evaluon.key: el certificado de $ADDRESS, para Caddy."
echo "  ca-evaluon.crt: la raíz, para instalar una vez en cada computadora de la lista."
echo
echo "Raíz (ca-evaluon.crt):"
echo "  Huella SHA-1 (la «Huella digital» que muestra Windows): $(openssl x509 -in "$CA_CRT" -noout -fingerprint -sha1 | hex)"
echo "  Huella SHA-256: $(openssl x509 -in "$CA_CRT" -noout -fingerprint -sha256 | hex)"
echo "  Vence: $(openssl x509 -in "$CA_CRT" -noout -enddate -dateopt iso_8601 | sed 's/^notAfter=//')"
echo "Certificado del servidor:"
echo "  Vence: $(openssl x509 -in "$RED/certificados/evaluon.crt" -noout -enddate -dateopt iso_8601 | sed 's/^notAfter=//') (renovarlo antes: volver a correr este script y reiniciar el servicio EVALUON-Caddy)"
