# Imagen de la aplicación de EVALUON: servicios `app` y `migrate` (plan 001, "Servicios").
# Python 3.12 sobre Debian 13 (trixie), fijada por etiqueta y huella; Tesseract con el
# modelo de español de tessdata_best verificado por huella. Sin PyTorch y sin GPU.
# Versiones y huellas: specs/001-normativa/entorno.md, T-005.

FROM python:3.12.15-slim-trixie@sha256:29113dcae7aad06daa8e95260fa09f27d62be33b9687ea3774f771d601a02256

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Tesseract 5.5 del repositorio de Debian. Sin los paquetes recomendados: el modelo de
# español no es el del paquete tesseract-ocr-spa (tessdata_fast) sino el de abajo.
# Pango, HarfBuzz y una tipografía para el PDF de la matriz con WeasyPrint (ADR-0020, T-086);
# la imagen slim no trae ninguna fuente. Versiones de Debian 13 fijadas.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr=5.5.0-1+b1 \
        libpango-1.0-0=1.56.3-1 \
        libpangoft2-1.0-0=1.56.3-1 \
        libharfbuzz-subset0=10.2.0-1+deb13u1 \
        fonts-dejavu-core=2.37-8 \
    && rm -rf /var/lib/apt/lists/*

# spa.traineddata de tessdata_best, versión 4.1.0 (commit e2aad9b9), verificado por huella
# SHA-256 al construir: si la huella no coincide, la construcción falla.
ADD --checksum=sha256:e2c1ffdad8b30f26c45d4017a9183d3a7f9aa69e59918be4f88b126fac99ab2c \
    https://raw.githubusercontent.com/tesseract-ocr/tessdata_best/e2aad9b983032bb1beff9133104a67cdbb87ca4d/spa.traineddata \
    /usr/share/tesseract-ocr/5/tessdata/spa.traineddata
RUN chmod 0644 /usr/share/tesseract-ocr/5/tessdata/spa.traineddata

RUN useradd --create-home --uid 1000 evaluon \
    && mkdir /app \
    && chown evaluon:evaluon /app
WORKDIR /app

# Dependencias con versión fija (pyproject.toml), incluidas las de prueba.
# Se instalan desde una copia aparte para no dejar archivos de construcción en /app.
COPY pyproject.toml /tmp/deps/
RUN pip install "/tmp/deps[test]" && rm -rf /tmp/deps

COPY --chown=evaluon:evaluon . .
USER evaluon

# Reúne los archivos estáticos que sirve WhiteNoise. collectstatic no usa la base ni la
# clave: los valores de abajo solo existen durante este paso.
RUN DJANGO_SECRET_KEY=collectstatic-only POSTGRES_PASSWORD=collectstatic-only \
    python manage.py collectstatic --noinput

EXPOSE 8000
CMD ["gunicorn", "evaluon.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "4", "--timeout", "120", "--access-logfile", "-"]
