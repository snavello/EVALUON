#!/usr/bin/env bash
# Descarga los archivos de los modelos en models/ y verifica su huella SHA-256
# contra scripts/models.sha256. Sin opciones baja la lista normal (Gemma 4 12B con su
# proyector de imagen, bge-m3 y el reranker). Con --modelo-grande baja, en cambio, solo
# la lista aparte del Gemma 4 26B-A4B y su proyector (15,6 GB; ADR-0042), que se usa
# únicamente en la comparación de modelos de la 004 con docker-compose.modelo-grande.yml.
# Con --qwen38-27b o --qwen36-35b baja, también aparte, el modelo candidato de la
# comparación de la 015 y su proyector de imagen (Qwen3.8-27B, 17,4 GB; Qwen3.6-35B-A3B,
# 18,6 GB; ADR-0056), que se usan con docker-compose.qwen38-27b.yml o
# docker-compose.qwen36-35b.yml. Las opciones no se combinan: una por corrida. Es el único
# paso del entorno que usa internet;
# se corre una vez por equipo. Si un archivo ya está y su huella coincide, no se
# vuelve a bajar. Para mudar el sistema también se puede copiar la carpeta models/.
#
# Variables de entorno opcionales:
#   MODELS_DIR       carpeta de destino (por defecto: models/ en la raíz del repositorio)
#   CURL_EXTRA_OPTS  opciones adicionales para curl (por ejemplo, --ssl-no-revoke en
#                    Windows cuando no se puede consultar la revocación de certificados)

set -euo pipefail

mode="normal"
for arg in "$@"; do
  case "$arg" in
    --modelo-grande|--qwen38-27b|--qwen36-35b)
      if [ "$mode" != "normal" ]; then
        echo "Usá una sola opción por corrida." >&2
        exit 2
      fi
      case "$arg" in
        --modelo-grande) mode="grande" ;;
        --qwen38-27b) mode="qwen38" ;;
        --qwen36-35b) mode="qwen36" ;;
      esac
      ;;
    *) echo "Uso: $0 [--modelo-grande | --qwen38-27b | --qwen36-35b]" >&2; exit 2 ;;
  esac
done

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
models_dir="${MODELS_DIR:-$repo_root/models}"
checksums="$repo_root/scripts/models.sha256"

# Origen de cada archivo: nombre local, URL fijada a una revisión del repositorio.
# Gemma 4 12B, 4 bits (QAT), publicado por Google (ADR-0002).
SOURCES=(
  "gemma-4-12b-it-qat-q4_0.gguf https://huggingface.co/google/gemma-4-12B-it-qat-q4_0-gguf/resolve/29d097773436b69ff9feafd636ab4cf873786537/gemma-4-12b-it-qat-q4_0.gguf"
  # Proyector de imagen del 12B, misma revisión (lectura con visión, ADR-0041).
  "mmproj-gemma-4-12b-it-qat-q4_0.gguf https://huggingface.co/google/gemma-4-12B-it-qat-q4_0-gguf/resolve/29d097773436b69ff9feafd636ab4cf873786537/mmproj-gemma-4-12b-it-qat-q4_0.gguf"
  # bge-m3 y bge-reranker-v2-m3 en FP16, conversiones GGUF de gpustack (ADR-0003, [F29] y [F30]).
  "bge-m3-FP16.gguf https://huggingface.co/gpustack/bge-m3-GGUF/resolve/2d48f1737679ad900d5c26c5aad5410e9c70fdca/bge-m3-FP16.gguf"
  "bge-reranker-v2-m3-FP16.gguf https://huggingface.co/gpustack/bge-reranker-v2-m3-GGUF/resolve/3093af03b1a635e67b084b1d8c03c5f5e020fd05/bge-reranker-v2-m3-FP16.gguf"
)

# Lista aparte, solo con --modelo-grande: Gemma 4 26B-A4B (QAT q4_0) de Google y su
# proyector de imagen, en la revisión fijada (ADR-0042).
LARGE_SOURCES=(
  "gemma-4-26B_q4_0-it.gguf https://huggingface.co/google/gemma-4-26B-A4B-it-qat-q4_0-gguf/resolve/d1c082be9cf3c8a514acf63b8761f4b41935842e/gemma-4-26B_q4_0-it.gguf"
  "gemma-4-26B-it-mmproj.gguf https://huggingface.co/google/gemma-4-26B-A4B-it-qat-q4_0-gguf/resolve/d1c082be9cf3c8a514acf63b8761f4b41935842e/gemma-4-26B-it-mmproj.gguf"
)

# Listas aparte de la comparación de la 015 (ADR-0056). Los modelos son de Unsloth (un
# tercero): la revisión fijada y la huella de scripts/models.sha256 compensan el origen.
# Los proyectores se llaman igual en los dos repositorios (mmproj-F16.gguf): el nombre
# local lleva el modelo para que no se pisen.
# Qwen3.8-27B (denso), UD-Q4_K_M, con su proyector de imagen F16.
QWEN38_SOURCES=(
  "Qwen3.8-27B-UD-Q4_K_M.gguf https://huggingface.co/unsloth/Qwen3.8-27B-GGUF/resolve/4ca720788d1e01f1bff70c033e0d0028fd02e502/Qwen3.8-27B-UD-Q4_K_M.gguf"
  "mmproj-Qwen3.8-27B-F16.gguf https://huggingface.co/unsloth/Qwen3.8-27B-GGUF/resolve/4ca720788d1e01f1bff70c033e0d0028fd02e502/mmproj-F16.gguf"
)

# Qwen3.6-35B-A3B (mezcla de expertos), UD-IQ4_XS, con su proyector de imagen F16.
QWEN36_SOURCES=(
  "Qwen3.6-35B-A3B-UD-IQ4_XS.gguf https://huggingface.co/unsloth/Qwen3.6-35B-A3B-GGUF/resolve/a483e9e6cbd595906af30beda3187c2663a1118c/Qwen3.6-35B-A3B-UD-IQ4_XS.gguf"
  "mmproj-Qwen3.6-35B-A3B-F16.gguf https://huggingface.co/unsloth/Qwen3.6-35B-A3B-GGUF/resolve/a483e9e6cbd595906af30beda3187c2663a1118c/mmproj-F16.gguf"
)

case "$mode" in
  grande) SOURCES=("${LARGE_SOURCES[@]}") ;;
  qwen38) SOURCES=("${QWEN38_SOURCES[@]}") ;;
  qwen36) SOURCES=("${QWEN36_SOURCES[@]}") ;;
esac

expected_hash() {
  awk -v f="$1" '$2 == f { print $1 }' "$checksums"
}

file_hash() {
  sha256sum "$1" | awk '{ print $1 }'
}

mkdir -p "$models_dir"
status=0

for entry in "${SOURCES[@]}"; do
  name="${entry%% *}"
  url="${entry#* }"
  target="$models_dir/$name"
  expected="$(expected_hash "$name")"

  if [ -z "$expected" ]; then
    echo "ERROR: $name no figura en $checksums" >&2
    status=1
    continue
  fi

  if [ -f "$target" ] && [ "$(file_hash "$target")" = "$expected" ]; then
    echo "OK (ya estaba): $name"
    continue
  fi

  echo "Descargando $name ..."
  # shellcheck disable=SC2086
  curl --fail --location --retry 10 --retry-delay 5 --retry-all-errors --continue-at - \
    ${CURL_EXTRA_OPTS:-} --output "$target.part" "$url"
  mv "$target.part" "$target"

  actual="$(file_hash "$target")"
  if [ "$actual" = "$expected" ]; then
    echo "OK: $name  sha256=$actual"
  else
    echo "ERROR: huella distinta para $name" >&2
    echo "  esperada: $expected" >&2
    echo "  obtenida: $actual" >&2
    status=1
  fi
done

exit "$status"
