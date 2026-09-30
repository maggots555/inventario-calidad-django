#!/bin/sh
# Arranque de SIGMA dentro del contenedor.
#
# EXPLICACIÓN PARA PRINCIPIANTES:
# Compose puede pedir "gunicorn" o "celery". Este script corre ANTES,
# para no arrancar la app contra una base que todavía no existe.
#
# 1. Espera a que PostgreSQL acepte conexiones.
# 2. Solo el contenedor web (SIGMA_MIGRAR=1) crea las tablas.
#    México vive en la base "default". Argentina, Chile y Colombia
#    tienen su propia base. "mexico" en Django apunta a la misma base
#    que "default", así que no se migra dos veces.
# 3. Junta CSS/JS en staticfiles para que Nginx los sirva.
# 4. Cede el sitio al comando real (gunicorn o celery).

set -eu

echo "Esperando a PostgreSQL en ${DB_HOST:-postgres}:${DB_PORT:-5432}..."

python - <<'PY'
import os
import sys
import time

import psycopg2

host = os.environ.get("DB_HOST", "postgres")
port = int(os.environ.get("DB_PORT", "5432"))
user = os.environ["DB_USER"]
password = os.environ["DB_PASSWORD"]
dbname = os.environ.get("DB_NAME", "inventario_mexico")

for intento in range(1, 31):
    try:
        conexion = psycopg2.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            dbname=dbname,
        )
        conexion.close()
        print(f"PostgreSQL listo (intento {intento}).")
        sys.exit(0)
    except Exception as exc:
        print(f"Intento {intento}/30: PostgreSQL aún no responde ({exc}).")
        time.sleep(2)

print("PostgreSQL no respondió a tiempo. Revisa usuario, clave y que el servicio postgres esté sano.")
sys.exit(1)
PY

if [ "${SIGMA_MIGRAR:-0}" = "1" ]; then
    echo "Aplicando migraciones en México (base default)..."
    python manage.py migrate --noinput

    echo "Aplicando migraciones en Argentina..."
    python manage.py migrate --database=argentina --noinput

    echo "Aplicando migraciones en Chile..."
    python manage.py migrate --database=chile --noinput

    echo "Aplicando migraciones en Colombia..."
    python manage.py migrate --database=colombia --noinput

    echo "Reuniendo archivos estáticos para Nginx..."
    python manage.py collectstatic --noinput
fi

exec "$@"
