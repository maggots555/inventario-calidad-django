# Imagen de SIGMA: compila el TypeScript y deja lista la app Django.
#
# EXPLICACIÓN PARA PRINCIPIANTES:
# Hay dos etapas. La primera solo existe para convertir static/ts en
# static/js (igual que "pnpm run build" en la laptop). La segunda es la
# imagen que realmente corre: Python 3.12, FFmpeg para los videos y
# las librerías de requirements.lock. El código de negocio no cambia.

# --- Etapa 1: JavaScript compilado ---
FROM node:22-bookworm-slim AS frontend

WORKDIR /src

RUN corepack enable && corepack prepare pnpm@11.3.0 --activate

COPY package.json pnpm-lock.yaml ./
COPY tsconfig.json tsconfig.sw.json tsconfig.jpeg_worker.json ./
COPY static/ts ./static/ts

RUN pnpm install --frozen-lockfile \
    && mkdir -p static/js \
    && pnpm run build

# --- Etapa 2: aplicación ---
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# FFmpeg lo usan las tareas de video (comprimir, resumen, evidencia).
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-docker.txt requirements.lock ./
RUN pip install --no-cache-dir -r requirements-docker.txt

COPY . .
COPY --from=frontend /src/static/js ./static/js

RUN mkdir -p /app/logs /app/media /app/staticfiles \
    && chmod +x /app/docker/entrypoint.sh /app/docker/postgres-init.sh

EXPOSE 8000

ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "120", "--access-logfile", "-", "--error-logfile", "-"]
